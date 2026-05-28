from __future__ import annotations

import json
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
DEFAULT_KUBE_GPU_REQUEST_QUERY = (
    'sum by (namespace, pod) '
    '(kube_pod_container_resource_requests{resource=~"nvidia_com_gpu|nvidia.com/gpu"})'
)
_OPENER = build_opener(ProxyHandler({}))


class PrometheusError(RuntimeError):
    pass


def query_range(
    prometheus_url: str,
    query: str,
    start: datetime,
    end: datetime,
    step: str,
    timeout: float = 20.0,
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
    request = Request(url, headers={"Accept": "application/json"})

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

    data = payload.get("data", {})
    if data.get("resultType") != "matrix":
        raise PrometheusError(f"Prometheus query did not return a range vector: {query}")

    return tuple(Series.from_prometheus(item) for item in data.get("result", []))


def collect_bundle(
    prometheus_url: str,
    hours: float,
    step: str,
    gpu_util_query: str = DEFAULT_GPU_UTIL_QUERY,
    memory_used_query: str = DEFAULT_MEMORY_USED_QUERY,
    memory_total_query: str = DEFAULT_MEMORY_TOTAL_QUERY,
    kube_gpu_request_query: str | None = DEFAULT_KUBE_GPU_REQUEST_QUERY,
    timeout: float = 20.0,
) -> MetricBundle:
    end = datetime.now(timezone.utc)
    start = datetime.fromtimestamp(end.timestamp() - hours * 3600, tz=timezone.utc)
    gpu_requests: tuple[Series, ...] = ()
    if kube_gpu_request_query:
        gpu_requests = query_range(
            prometheus_url, kube_gpu_request_query, start, end, step, timeout=timeout
        )

    return MetricBundle(
        gpu_utilization=query_range(
            prometheus_url, gpu_util_query, start, end, step, timeout=timeout
        ),
        memory_used=query_range(
            prometheus_url, memory_used_query, start, end, step, timeout=timeout
        ),
        memory_total=query_range(
            prometheus_url, memory_total_query, start, end, step, timeout=timeout
        ),
        gpu_requests=gpu_requests,
    )


def load_bundle(path: Path) -> MetricBundle:
    with path.open("r", encoding="utf-8") as stream:
        payload: dict[str, Any] = json.load(stream)
    return MetricBundle.from_mapping(payload)
