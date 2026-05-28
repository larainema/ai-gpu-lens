from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable

from .i18n import DEFAULT_LANGUAGE, normalize_language, t
from .model import (
    AuditReport,
    GpuSummary,
    MetricBundle,
    NamespaceSummary,
    Series,
    WorkloadRequestSummary,
)


UNKNOWN = "unknown"


def analyze_bundle(
    bundle: MetricBundle,
    *,
    window_hours: float,
    step: str,
    price_per_gpu_hour: float = 0.0,
    gpu_prices: dict[str, float] | None = None,
    idle_threshold: float = 5.0,
    active_threshold: float = 10.0,
    language: str = DEFAULT_LANGUAGE,
) -> AuditReport:
    language = normalize_language(language)
    gpu_prices = gpu_prices or {}
    memory_used = _latest_series_by_gpu(bundle.memory_used)
    memory_total = _latest_series_by_gpu(bundle.memory_total)
    gpus: list[GpuSummary] = []
    namespace_util_stats: dict[str, list[tuple[float, float]]] = defaultdict(list)
    telemetry_gaps: set[str] = set()

    for key, series_group in _group_series_by_gpu(bundle.gpu_utilization).items():
        series = _dedupe_gpu_series(key, series_group)
        if not series.values:
            continue
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

        namespace = shared_label_value(series_group, ("namespace", "exported_namespace"))
        pod = shared_label_value(series_group, ("pod", "pod_name", "exported_pod"))
        if namespace == UNKNOWN:
            telemetry_gaps.add(t(language, "gap_no_namespace_labels"))
        if pod == UNKNOWN:
            telemetry_gaps.add(t(language, "gap_no_pod_labels"))
        if key not in memory_used:
            telemetry_gaps.add(t(language, "gap_no_memory_used"))
        if key not in memory_total:
            telemetry_gaps.add(t(language, "gap_no_memory_total"))

        model = shared_label_value(series_group, ("modelName", "model", "gpu_model"))
        price = price_for_model(model, gpu_prices, price_per_gpu_hour)
        namespace_util_stats[namespace].append((avg_util, observed_hours))
        gpus.append(
            GpuSummary(
                gpu_id=key,
                node=node_name(series.metric),
                uuid=label_value(series.metric, ("UUID", "uuid", "gpu_uuid")),
                index=label_value(series.metric, ("gpu", "device", "minor_number")),
                model=model,
                namespace=namespace,
                pod=pod,
                avg_utilization=avg_util,
                max_utilization=max_util,
                active_ratio=active_ratio,
                idle_hours=idle_hours,
                observed_hours=observed_hours,
                avg_memory_percent=avg_memory_percent,
                max_memory_percent=max_memory_percent,
                price_per_gpu_hour=price,
                estimated_idle_cost=idle_hours * price,
                source_series_count=len(series_group),
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
    estimated_idle_cost = sum(gpu.estimated_idle_cost for gpu in gpus)
    workload_requests = build_workload_requests(
        bundle.gpu_requests,
        window_hours=window_hours,
        default_price_per_gpu_hour=price_per_gpu_hour,
    )
    total_requested_gpu_hours = sum(
        item.requested_gpu_hours for item in workload_requests
    )
    estimated_request_cost = sum(
        item.estimated_request_cost for item in workload_requests
    )
    request_by_namespace: dict[str, tuple[float, float]] = defaultdict(lambda: (0.0, 0.0))
    for item in workload_requests:
        requested_hours, requested_cost = request_by_namespace[item.namespace]
        request_by_namespace[item.namespace] = (
            requested_hours + item.requested_gpu_hours,
            requested_cost + item.estimated_request_cost,
        )

    namespaces = [
        NamespaceSummary(
            namespace=namespace,
            utilized_gpu_hour_equivalent=sum(
                (avg_util / 100.0) * observed_hours
                for avg_util, observed_hours in samples
            ),
            requested_gpu_hours=request_by_namespace[namespace][0],
            estimated_request_cost=request_by_namespace[namespace][1],
            series_count=len(samples),
            avg_utilization=(
                sum(avg_util * observed_hours for avg_util, observed_hours in samples)
                / sum(observed_hours for _, observed_hours in samples)
            )
            if sum(observed_hours for _, observed_hours in samples)
            else 0.0,
        )
        for namespace, samples in namespace_util_stats.items()
    ]
    util_namespaces = {item.namespace for item in namespaces}
    for namespace, (requested_hours, requested_cost) in request_by_namespace.items():
        if namespace in util_namespaces:
            continue
        namespaces.append(
            NamespaceSummary(
                namespace=namespace,
                requested_gpu_hours=requested_hours,
                estimated_request_cost=requested_cost,
            )
        )
    namespaces.sort(
        key=lambda item: (
            item.estimated_request_cost,
            item.requested_gpu_hours,
            item.utilized_gpu_hour_equivalent,
        ),
        reverse=True,
    )
    if bundle.gpu_utilization and any(gpu.source_series_count > 1 for gpu in gpus):
        telemetry_gaps.add(t(language, "gap_deduped_gpu_series"))
    if not bundle.gpu_requests:
        telemetry_gaps.add(t(language, "gap_no_kube_gpu_requests"))

    recommendations = build_recommendations(
        gpus,
        fleet_avg_utilization=fleet_avg,
        total_idle_gpu_hours=total_idle_hours,
        total_requested_gpu_hours=total_requested_gpu_hours,
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
        gpu_prices=dict(sorted(gpu_prices.items())),
        total_gpus=len(gpus),
        total_requested_gpu_hours=total_requested_gpu_hours,
        fleet_avg_utilization=fleet_avg,
        total_idle_gpu_hours=total_idle_hours,
        estimated_idle_cost=estimated_idle_cost,
        estimated_request_cost=estimated_request_cost,
        gpus=gpus,
        namespaces=namespaces,
        workload_requests=workload_requests,
        recommendations=recommendations,
        telemetry_gaps=sorted(telemetry_gaps),
    )


def build_recommendations(
    gpus: list[GpuSummary],
    *,
    fleet_avg_utilization: float,
    total_idle_gpu_hours: float,
    total_requested_gpu_hours: float,
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
                cost=sum(gpu.estimated_idle_cost for gpu in gpus),
            )
        )
    if total_requested_gpu_hours > 0:
        recommendations.append(
            t(
                language,
                "rec_compare_requests",
                requested_hours=total_requested_gpu_hours,
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


def build_workload_requests(
    series_list: tuple[Series, ...],
    *,
    window_hours: float,
    default_price_per_gpu_hour: float,
) -> list[WorkloadRequestSummary]:
    summaries: list[WorkloadRequestSummary] = []
    for series in series_list:
        if not series.values:
            continue
        values = [max(0.0, value) for _, value in series.values]
        avg_requested = sum(values) / len(values)
        observed_hours = _observed_hours(series, fallback_hours=window_hours)
        requested_gpu_hours = avg_requested * observed_hours
        summaries.append(
            WorkloadRequestSummary(
                namespace=label_value(series.metric, ("namespace",)),
                pod=label_value(series.metric, ("pod", "pod_name")),
                avg_requested_gpus=avg_requested,
                requested_gpu_hours=requested_gpu_hours,
                estimated_request_cost=requested_gpu_hours * default_price_per_gpu_hour,
                samples=len(values),
            )
        )
    summaries.sort(
        key=lambda item: (item.estimated_request_cost, item.requested_gpu_hours),
        reverse=True,
    )
    return summaries


def _group_series_by_gpu(
    series_list: tuple[Series, ...],
) -> dict[str, list[Series]]:
    groups: dict[str, list[Series]] = defaultdict(list)
    for series in series_list:
        if series.values:
            groups[gpu_key(series.metric)].append(series)
    return groups


def _dedupe_gpu_series(key: str, series_group: list[Series]) -> Series:
    if len(series_group) == 1:
        return series_group[0]
    values_by_timestamp: dict[float, float] = {}
    for series in series_group:
        for timestamp, value in series.values:
            values_by_timestamp[timestamp] = max(
                values_by_timestamp.get(timestamp, value),
                value,
            )
    labels = dict(series_group[0].metric)
    labels["dedupe_key"] = key
    return Series(
        metric=labels,
        values=tuple(sorted(values_by_timestamp.items())),
    )


def price_for_model(
    model: str,
    gpu_prices: dict[str, float],
    default_price_per_gpu_hour: float,
) -> float:
    if not gpu_prices:
        return default_price_per_gpu_hour
    normalized_model = model.lower()
    exact = {
        configured_model.lower(): price
        for configured_model, price in gpu_prices.items()
        if configured_model.lower() not in {"default", "*"}
    }
    if normalized_model in exact:
        return exact[normalized_model]
    for configured_model in sorted(exact, key=len, reverse=True):
        if configured_model in normalized_model or normalized_model in configured_model:
            return exact[configured_model]
    return gpu_prices.get("default", gpu_prices.get("*", default_price_per_gpu_hour))


def shared_label_value(series_group: list[Series], candidates: tuple[str, ...]) -> str:
    values = {
        label_value(series.metric, candidates)
        for series in series_group
        if label_value(series.metric, candidates) != UNKNOWN
    }
    if not values:
        return UNKNOWN
    if len(values) == 1:
        return next(iter(values))
    return "mixed"


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
