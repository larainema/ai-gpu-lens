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
    estimated_idle_cost: float = 0.0
    samples: int = 0


@dataclass
class NamespaceSummary:
    namespace: str
    utilized_gpu_hour_equivalent: float = 0.0
    series_count: int = 0
    avg_utilization: float = 0.0


@dataclass
class AuditReport:
    generated_at: str
    language: str
    window_hours: float
    step: str
    price_per_gpu_hour: float
    total_gpus: int
    fleet_avg_utilization: float
    total_idle_gpu_hours: float
    estimated_idle_cost: float
    gpus: list[GpuSummary] = field(default_factory=list)
    namespaces: list[NamespaceSummary] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    telemetry_gaps: list[str] = field(default_factory=list)
