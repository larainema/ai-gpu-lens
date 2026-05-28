from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from .prometheus import (
    DEFAULT_GPU_UTIL_QUERY,
    DEFAULT_KUBE_GPU_REQUEST_QUERY,
    DEFAULT_MEMORY_TOTAL_QUERY,
    DEFAULT_MEMORY_USED_QUERY,
    PrometheusError,
    query_instant,
)


@dataclass
class DoctorCheck:
    name: str
    status: str
    message: str
    count: float | None = None


@dataclass
class DoctorReport:
    generated_at: str
    prometheus_url: str
    checks: list[DoctorCheck] = field(default_factory=list)
    gpu_models: list[dict[str, object]] = field(default_factory=list)
    suggested_queries: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def run_doctor(
    prometheus_url: str,
    *,
    timeout: float = 20.0,
    basic_auth: tuple[str, str] | None = None,
    bearer_token: str | None = None,
) -> DoctorReport:
    checks: list[DoctorCheck] = []
    checks.append(
        count_check(
            prometheus_url,
            "dcgm_gpu_utilization",
            f"count({DEFAULT_GPU_UTIL_QUERY})",
            "DCGM GPU utilization series",
            timeout=timeout,
            basic_auth=basic_auth,
            bearer_token=bearer_token,
        )
    )
    checks.append(
        count_check(
            prometheus_url,
            "dcgm_memory_used",
            f"count({DEFAULT_MEMORY_USED_QUERY})",
            "DCGM framebuffer memory used series",
            timeout=timeout,
            basic_auth=basic_auth,
            bearer_token=bearer_token,
        )
    )
    checks.append(
        count_check(
            prometheus_url,
            "dcgm_memory_total",
            f"count({DEFAULT_MEMORY_TOTAL_QUERY})",
            "DCGM framebuffer memory total series",
            timeout=timeout,
            basic_auth=basic_auth,
            bearer_token=bearer_token,
        )
    )
    checks.append(
        count_check(
            prometheus_url,
            "dcgm_memory_free",
            "count(DCGM_FI_DEV_FB_FREE)",
            "DCGM framebuffer memory free series",
            ok_when_zero=True,
            timeout=timeout,
            basic_auth=basic_auth,
            bearer_token=bearer_token,
        )
    )
    checks.append(
        count_check(
            prometheus_url,
            "kube_gpu_requests",
            f"count({DEFAULT_KUBE_GPU_REQUEST_QUERY})",
            "active kube-state-metrics GPU request series",
            timeout=timeout,
            basic_auth=basic_auth,
            bearer_token=bearer_token,
        )
    )
    checks.append(
        count_check(
            prometheus_url,
            "dcgm_exported_workload_labels",
            f'count({DEFAULT_GPU_UTIL_QUERY}{{exported_namespace!=""}})',
            "DCGM exported workload namespace labels",
            ok_when_zero=True,
            timeout=timeout,
            basic_auth=basic_auth,
            bearer_token=bearer_token,
        )
    )
    gpu_models = gpu_model_distribution(
        prometheus_url,
        timeout=timeout,
        basic_auth=basic_auth,
        bearer_token=bearer_token,
    )
    return DoctorReport(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        prometheus_url=prometheus_url,
        checks=checks,
        gpu_models=gpu_models,
        suggested_queries={
            "gpu_util_query": DEFAULT_GPU_UTIL_QUERY,
            "memory_used_query": DEFAULT_MEMORY_USED_QUERY,
            "memory_total_query": DEFAULT_MEMORY_TOTAL_QUERY,
            "memory_total_fallback_query": (
                "DCGM_FI_DEV_FB_USED + ignoring(__name__) DCGM_FI_DEV_FB_FREE"
            ),
            "kube_gpu_request_query": DEFAULT_KUBE_GPU_REQUEST_QUERY,
        },
    )


def count_check(
    prometheus_url: str,
    name: str,
    query: str,
    label: str,
    *,
    ok_when_zero: bool = False,
    timeout: float,
    basic_auth: tuple[str, str] | None,
    bearer_token: str | None,
) -> DoctorCheck:
    try:
        series = query_instant(
            prometheus_url,
            query,
            timeout=timeout,
            basic_auth=basic_auth,
            bearer_token=bearer_token,
        )
    except PrometheusError as exc:
        return DoctorCheck(name=name, status="error", message=str(exc))
    count = series[0].values[0][1] if series and series[0].values else 0.0
    if count > 0:
        return DoctorCheck(
            name=name,
            status="ok",
            count=count,
            message=f"{label}: {count:g}",
        )
    status = "ok" if ok_when_zero else "warn"
    return DoctorCheck(
        name=name,
        status=status,
        count=count,
        message=f"{label}: none found",
    )


def gpu_model_distribution(
    prometheus_url: str,
    *,
    timeout: float,
    basic_auth: tuple[str, str] | None,
    bearer_token: str | None,
) -> list[dict[str, object]]:
    try:
        series = query_instant(
            prometheus_url,
            f"count by (Hostname, modelName) ({DEFAULT_GPU_UTIL_QUERY})",
            timeout=timeout,
            basic_auth=basic_auth,
            bearer_token=bearer_token,
        )
    except PrometheusError:
        return []
    items = []
    for item in series:
        value = item.values[0][1] if item.values else 0.0
        items.append(
            {
                "hostname": item.metric.get("Hostname", "unknown"),
                "model": item.metric.get("modelName", "unknown"),
                "count": value,
            }
        )
    items.sort(key=lambda item: (str(item["model"]), str(item["hostname"])))
    return items


def render_doctor_text(report: DoctorReport) -> str:
    lines = [
        "ai-gpu-lens doctor",
        f"endpoint: {report.prometheus_url}",
        f"generated: {report.generated_at}",
        "",
        "checks:",
    ]
    for check in report.checks:
        lines.append(f"- [{check.status.upper()}] {check.name}: {check.message}")
    lines.append("")
    lines.append("gpu model distribution:")
    if report.gpu_models:
        for item in report.gpu_models:
            lines.append(
                f"- {item['hostname']}: {item['model']} x {item['count']:g}"
            )
    else:
        lines.append("- n/a")
    lines.append("")
    lines.append("suggested queries:")
    for name, query in report.suggested_queries.items():
        lines.append(f"- {name}: {query}")
    return "\n".join(lines)
