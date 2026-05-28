from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable

from .i18n import DEFAULT_LANGUAGE, normalize_language, t
from .model import AuditReport, GpuSummary, MetricBundle, NamespaceSummary, Series


UNKNOWN = "unknown"


def analyze_bundle(
    bundle: MetricBundle,
    *,
    window_hours: float,
    step: str,
    price_per_gpu_hour: float = 0.0,
    idle_threshold: float = 5.0,
    active_threshold: float = 10.0,
    language: str = DEFAULT_LANGUAGE,
) -> AuditReport:
    language = normalize_language(language)
    memory_used = _latest_series_by_gpu(bundle.memory_used)
    memory_total = _latest_series_by_gpu(bundle.memory_total)
    gpus: list[GpuSummary] = []
    namespace_stats: dict[str, list[tuple[float, float]]] = defaultdict(list)
    telemetry_gaps: set[str] = set()

    for series in bundle.gpu_utilization:
        if not series.values:
            continue
        key = gpu_key(series.metric)
        values = [value for _, value in series.values]
        avg_util = sum(values) / len(values)
        max_util = max(values)
        active_ratio = _ratio(values, lambda value: value >= active_threshold)
        idle_ratio = _ratio(values, lambda value: value < idle_threshold)
        observed_hours = _observed_hours(series, fallback_hours=window_hours)
        idle_hours = observed_hours * idle_ratio

        used = memory_used.get(key)
        total = memory_total.get(key)
        avg_memory_percent = None
        max_memory_percent = None
        if used and total:
            used_values = [value for _, value in used.values]
            total_values = [value for _, value in total.values if value > 0]
            if used_values and total_values:
                total_value = max(total_values)
                memory_percents = [(value / total_value) * 100 for value in used_values]
                avg_memory_percent = sum(memory_percents) / len(memory_percents)
                max_memory_percent = max(memory_percents)

        namespace = label_value(series.metric, ("namespace", "exported_namespace"))
        pod = label_value(series.metric, ("pod", "pod_name", "exported_pod"))
        if namespace == UNKNOWN:
            telemetry_gaps.add(t(language, "gap_no_namespace_labels"))
        if pod == UNKNOWN:
            telemetry_gaps.add(t(language, "gap_no_pod_labels"))
        if key not in memory_used:
            telemetry_gaps.add(t(language, "gap_no_memory_used"))
        if key not in memory_total:
            telemetry_gaps.add(t(language, "gap_no_memory_total"))

        namespace_stats[namespace].append((avg_util, observed_hours))
        gpus.append(
            GpuSummary(
                gpu_id=key,
                node=node_name(series.metric),
                uuid=label_value(series.metric, ("UUID", "uuid", "gpu_uuid")),
                index=label_value(series.metric, ("gpu", "device", "minor_number")),
                model=label_value(series.metric, ("modelName", "model", "gpu_model")),
                namespace=namespace,
                pod=pod,
                avg_utilization=avg_util,
                max_utilization=max_util,
                active_ratio=active_ratio,
                idle_hours=idle_hours,
                observed_hours=observed_hours,
                avg_memory_percent=avg_memory_percent,
                max_memory_percent=max_memory_percent,
                estimated_idle_cost=idle_hours * price_per_gpu_hour,
                samples=len(values),
            )
        )

    gpus.sort(key=lambda gpu: (gpu.node, gpu.index, gpu.uuid, gpu.namespace, gpu.pod))
    total_observed_hours = sum(gpu.observed_hours for gpu in gpus)
    weighted_utilization = sum(gpu.avg_utilization * gpu.observed_hours for gpu in gpus)
    fleet_avg = (
        weighted_utilization / total_observed_hours if total_observed_hours else 0.0
    )
    total_idle_hours = sum(gpu.idle_hours for gpu in gpus)
    estimated_idle_cost = total_idle_hours * price_per_gpu_hour

    namespaces = [
        NamespaceSummary(
            namespace=namespace,
            utilized_gpu_hour_equivalent=sum(
                (avg_util / 100.0) * observed_hours
                for avg_util, observed_hours in samples
            ),
            series_count=len(samples),
            avg_utilization=(
                sum(avg_util * observed_hours for avg_util, observed_hours in samples)
                / sum(observed_hours for _, observed_hours in samples)
            )
            if sum(observed_hours for _, observed_hours in samples)
            else 0.0,
        )
        for namespace, samples in namespace_stats.items()
    ]
    namespaces.sort(
        key=lambda item: item.utilized_gpu_hour_equivalent,
        reverse=True,
    )

    recommendations = build_recommendations(
        gpus,
        fleet_avg_utilization=fleet_avg,
        total_idle_gpu_hours=total_idle_hours,
        price_per_gpu_hour=price_per_gpu_hour,
        telemetry_gaps=telemetry_gaps,
        language=language,
    )

    return AuditReport(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        language=language,
        window_hours=window_hours,
        step=step,
        price_per_gpu_hour=price_per_gpu_hour,
        total_gpus=len(gpus),
        fleet_avg_utilization=fleet_avg,
        total_idle_gpu_hours=total_idle_hours,
        estimated_idle_cost=estimated_idle_cost,
        gpus=gpus,
        namespaces=namespaces,
        recommendations=recommendations,
        telemetry_gaps=sorted(telemetry_gaps),
    )


def build_recommendations(
    gpus: list[GpuSummary],
    *,
    fleet_avg_utilization: float,
    total_idle_gpu_hours: float,
    price_per_gpu_hour: float,
    telemetry_gaps: set[str],
    language: str = DEFAULT_LANGUAGE,
) -> list[str]:
    recommendations: list[str] = []
    idle_gpus = [gpu for gpu in gpus if gpu.avg_utilization < 5.0]
    low_util_gpus = [
        gpu for gpu in gpus if gpu.avg_utilization < 20.0 and gpu.max_utilization < 50.0
    ]

    if idle_gpus:
        recommendations.append(
            t(language, "rec_investigate_idle_gpus", count=len(idle_gpus))
        )
    if low_util_gpus:
        recommendations.append(t(language, "rec_review_binpacking"))
    if fleet_avg_utilization < 35.0 and gpus:
        recommendations.append(t(language, "rec_low_fleet_utilization"))
    if total_idle_gpu_hours > 0 and price_per_gpu_hour > 0:
        recommendations.append(
            t(
                language,
                "rec_idle_cost",
                cost=total_idle_gpu_hours * price_per_gpu_hour,
            )
        )
    if any(gpu.avg_memory_percent is None for gpu in gpus):
        recommendations.append(t(language, "rec_add_memory_metrics"))
    if telemetry_gaps:
        recommendations.append(t(language, "rec_enable_k8s_labels"))
    if not recommendations:
        recommendations.append(t(language, "rec_no_major_waste"))
    return recommendations


def _latest_series_by_gpu(series_list: tuple[Series, ...]) -> dict[str, Series]:
    series_by_gpu: dict[str, Series] = {}
    for series in series_list:
        if series.values:
            series_by_gpu[gpu_key(series.metric)] = series
    return series_by_gpu


def _ratio(values: list[float], predicate: Callable[[float], bool]) -> float:
    if not values:
        return 0.0
    return sum(1 for value in values if predicate(value)) / len(values)


def _observed_hours(series: Series, *, fallback_hours: float) -> float:
    if len(series.values) < 2:
        return fallback_hours
    start = series.values[0][0]
    end = series.values[-1][0]
    observed = max(0.0, (end - start) / 3600.0)
    return observed or fallback_hours


def label_value(labels: dict[str, str], candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        value = labels.get(candidate)
        if value:
            return value
    return UNKNOWN


def node_name(labels: dict[str, str]) -> str:
    return label_value(
        labels,
        (
            "node",
            "kubernetes_node",
            "Hostname",
            "hostname",
            "instance",
        ),
    )


def gpu_key(labels: dict[str, str]) -> str:
    node = node_name(labels)
    uuid = label_value(labels, ("UUID", "uuid", "gpu_uuid"))
    index = label_value(labels, ("gpu", "device", "minor_number"))
    if uuid != UNKNOWN:
        return f"{node}/{uuid}"
    return f"{node}/gpu-{index}"
