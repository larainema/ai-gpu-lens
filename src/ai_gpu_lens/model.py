from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Series:
    """One Prometheus matrix series."""

    metric: dict[str, str]
    values: tuple[tuple[float, float], ...]

    @classmethod
    def from_prometheus(cls, item: dict[str, Any]) -> "Series":
        metric = {str(k): str(v) for k, v in item.get("metric", {}).items()}
        parsed: list[tuple[float, float]] = []
        for raw_ts, raw_value in item.get("values", []):
            try:
                value = float(raw_value)
                ts = float(raw_ts)
            except (TypeError, ValueError):
                continue
            if value != value:
                continue
            parsed.append((ts, value))
        return cls(metric=metric, values=tuple(parsed))


@dataclass(frozen=True)
class MetricBundle:
    gpu_utilization: tuple[Series, ...] = ()
    memory_used: tuple[Series, ...] = ()
    memory_total: tuple[Series, ...] = ()
    gpu_requests: tuple[Series, ...] = ()

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "MetricBundle":
        return cls(
            gpu_utilization=tuple(
                Series.from_prometheus(item)
                for item in payload.get("gpu_utilization", [])
            ),
            memory_used=tuple(
                Series.from_prometheus(item) for item in payload.get("memory_used", [])
            ),
            memory_total=tuple(
                Series.from_prometheus(item) for item in payload.get("memory_total", [])
            ),
            gpu_requests=tuple(
                Series.from_prometheus(item) for item in payload.get("gpu_requests", [])
            ),
        )


@dataclass
class GpuSummary:
    gpu_id: str
    node: str
    uuid: str
    index: str
    model: str
    namespace: str
    pod: str
    avg_utilization: float
    max_utilization: float
    active_ratio: float
    idle_hours: float
    observed_hours: float
    avg_memory_percent: float | None = None
    max_memory_percent: float | None = None
    price_per_gpu_hour: float = 0.0
    estimated_idle_cost: float = 0.0
    source_series_count: int = 1
    samples: int = 0


@dataclass
class NamespaceSummary:
    namespace: str
    utilized_gpu_hour_equivalent: float = 0.0
    requested_gpu_hours: float = 0.0
    over_requested_gpu_hours: float = 0.0
    estimated_request_cost: float = 0.0
    estimated_over_request_cost: float = 0.0
    series_count: int = 0
    avg_utilization: float = 0.0


@dataclass
class WorkloadRequestSummary:
    namespace: str
    pod: str
    avg_requested_gpus: float
    requested_gpu_hours: float
    estimated_request_cost: float
    utilized_gpu_hour_equivalent: float = 0.0
    over_requested_gpu_hours: float = 0.0
    estimated_over_request_cost: float = 0.0
    samples: int = 0


@dataclass
class GpuModelSummary:
    model: str
    count: int
    avg_utilization: float
    total_idle_gpu_hours: float
    estimated_idle_cost: float
    price_per_gpu_hour: float


@dataclass
class ActionItem:
    priority: str
    category: str
    target: str
    action: str
    estimated_window_savings: float = 0.0
    confidence: str = ""
    evidence: list[str] = field(default_factory=list)
    validation: str = ""


@dataclass
class AuditReport:
    generated_at: str
    language: str
    window_hours: float
    step: str
    price_per_gpu_hour: float
    gpu_prices: dict[str, float]
    total_gpus: int
    total_requested_gpu_hours: float
    fleet_avg_utilization: float
    total_idle_gpu_hours: float
    estimated_idle_cost: float
    estimated_request_cost: float
    gpus: list[GpuSummary] = field(default_factory=list)
    gpu_models: list[GpuModelSummary] = field(default_factory=list)
    namespaces: list[NamespaceSummary] = field(default_factory=list)
    workload_requests: list[WorkloadRequestSummary] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    telemetry_gaps: list[str] = field(default_factory=list)
