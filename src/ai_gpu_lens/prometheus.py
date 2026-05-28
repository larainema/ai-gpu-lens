from __future__ import annotations

import json
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

from .model import MetricBundle, Series


DEFAULT_GPU_UTIL_QUERY = "DCGM_FI_DEV_GPU_UTIL"
DEFAULT_MEMORY_USED_QUERY = "DCGM_FI_DEV_FB_USED"
DEFAULT_MEMORY_TOTAL_QUERY = "DCGM_FI_DEV_FB_TOTAL"
DEFAULT_MEMORY_TOTAL_FALLBACK_QUERY = (
    "DCGM_FI_DEV_FB_USED + ignoring(__name__) DCGM_FI_DEV_FB_FREE"
)
DEFAULT_KUBE_GPU_REQUEST_QUERY = (
    'sum by (namespace, pod) '
    '('
    'kube_pod_container_resource_requests{resource=~"nvidia_com_gpu|nvidia.com/gpu"} '
    '* on(namespace, pod) group_left() '
    'max by (namespace, pod) '
    '(kube_pod_status_phase{phase=~"Pending|Running"} == 1)'
    ')'
)
_OPENER = build_opener(ProxyHandler({}))


class PrometheusError(RuntimeError):
    pass


def query_instant(
    prometheus_url: str,
    query: str,
    timeout: float = 20.0,
    basic_auth: tuple[str, str] | None = None,
    bearer_token: str | None = None,
) -> tuple[Series, ...]:
    base = prometheus_url.rstrip("/")
    params = urlencode({"query": query})
    url = f"{base}/api/v1/query?{params}"
    payload = _query_json(
        url,
        query,
        timeout=timeout,
        basic_auth=basic_auth,
        bearer_token=bearer_token,
    )
    data = payload.get("data", {})
    if data.get("resultType") != "vector":
        raise PrometheusError(f"Prometheus query did not return an instant vector: {query}")
    series: list[Series] = []
    for item in data.get("result", []):
        metric = {str(k): str(v) for k, v in item.get("metric", {}).items()}
        raw_value = item.get("value", ())
        if len(raw_value) != 2:
            continue
        try:
            timestamp = float(raw_value[0])
            value = float(raw_value[1])
        except (TypeError, ValueError):
            continue
        series.append(Series(metric=metric, values=((timestamp, value),)))
    return tuple(series)


def query_range(
    prometheus_url: str,
    query: str,
    start: datetime,
    end: datetime,
    step: str,
    timeout: float = 20.0,
    basic_auth: tuple[str, str] | None = None,
    bearer_token: str | None = None,
) -> tuple[Series, ...]:
    base = prometheus_url.rstrip("/")
    params = urlencode(
        {
            "query": query,
            "start": str(int(start.timestamp())),
            "end": str(int(end.timestamp())),
            "step": step,
        }
    )
    url = f"{base}/api/v1/query_range?{params}"
    payload = _query_json(
        url,
        query,
        timeout=timeout,
        basic_auth=basic_auth,
        bearer_token=bearer_token,
    )

    data = payload.get("data", {})
    if data.get("resultType") != "matrix":
        raise PrometheusError(f"Prometheus query did not return a range vector: {query}")

    return tuple(Series.from_prometheus(item) for item in data.get("result", []))


def _query_json(
    url: str,
    query: str,
    *,
    timeout: float,
    basic_auth: tuple[str, str] | None,
    bearer_token: str | None,
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    if basic_auth:
        username, password = basic_auth
        token = b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    request = Request(url, headers=headers)

    try:
        with _OPENER.open(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise PrometheusError(f"Prometheus returned HTTP {exc.code} for {query}") from exc
    except URLError as exc:
        raise PrometheusError(f"Could not reach Prometheus: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise PrometheusError("Prometheus returned invalid JSON") from exc

    if payload.get("status") != "success":
        message = payload.get("error") or payload.get("errorType") or "unknown error"
        raise PrometheusError(f"Prometheus query failed for {query}: {message}")
    return payload


def collect_bundle(
    prometheus_url: str,
    hours: float,
    step: str,
    gpu_util_query: str = DEFAULT_GPU_UTIL_QUERY,
    memory_used_query: str = DEFAULT_MEMORY_USED_QUERY,
    memory_total_query: str = DEFAULT_MEMORY_TOTAL_QUERY,
    memory_total_fallback_query: str | None = DEFAULT_MEMORY_TOTAL_FALLBACK_QUERY,
    kube_gpu_request_query: str | None = DEFAULT_KUBE_GPU_REQUEST_QUERY,
    timeout: float = 20.0,
    basic_auth: tuple[str, str] | None = None,
    bearer_token: str | None = None,
) -> MetricBundle:
    end = datetime.now(timezone.utc)
    start = datetime.fromtimestamp(end.timestamp() - hours * 3600, tz=timezone.utc)
    gpu_requests: tuple[Series, ...] = ()
    if kube_gpu_request_query:
        gpu_requests = query_range(
            prometheus_url,
            kube_gpu_request_query,
            start,
            end,
            step,
            timeout=timeout,
            basic_auth=basic_auth,
            bearer_token=bearer_token,
        )

    memory_total = query_range_with_fallback(
        prometheus_url,
        memory_total_query,
        memory_total_fallback_query,
        start,
        end,
        step,
        timeout=timeout,
        basic_auth=basic_auth,
        bearer_token=bearer_token,
    )

    return MetricBundle(
        gpu_utilization=query_range(
            prometheus_url,
            gpu_util_query,
            start,
            end,
            step,
            timeout=timeout,
            basic_auth=basic_auth,
            bearer_token=bearer_token,
        ),
        memory_used=query_range(
            prometheus_url,
            memory_used_query,
            start,
            end,
            step,
            timeout=timeout,
            basic_auth=basic_auth,
            bearer_token=bearer_token,
        ),
        memory_total=memory_total,
        gpu_requests=gpu_requests,
    )


def query_range_with_fallback(
    prometheus_url: str,
    query: str,
    fallback_query: str | None,
    start: datetime,
    end: datetime,
    step: str,
    timeout: float = 20.0,
    basic_auth: tuple[str, str] | None = None,
    bearer_token: str | None = None,
) -> tuple[Series, ...]:
    try:
        primary = query_range(
            prometheus_url,
            query,
            start,
            end,
            step,
            timeout=timeout,
            basic_auth=basic_auth,
            bearer_token=bearer_token,
        )
    except PrometheusError as exc:
        if not fallback_query:
            raise
        try:
            return query_range(
                prometheus_url,
                fallback_query,
                start,
                end,
                step,
                timeout=timeout,
                basic_auth=basic_auth,
                bearer_token=bearer_token,
            )
        except PrometheusError:
            raise exc

    if primary or not fallback_query:
        return primary
    try:
        fallback = query_range(
            prometheus_url,
            fallback_query,
            start,
            end,
            step,
            timeout=timeout,
            basic_auth=basic_auth,
            bearer_token=bearer_token,
        )
    except PrometheusError:
        return primary
    return fallback or primary


def load_bundle(path: Path) -> MetricBundle:
    with path.open("r", encoding="utf-8") as stream:
        payload: dict[str, Any] = json.load(stream)
    return MetricBundle.from_mapping(payload)
