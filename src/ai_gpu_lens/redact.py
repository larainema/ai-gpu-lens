from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .model import (
    ActionItem,
    AuditReport,
    GpuModelSummary,
    GpuSummary,
    NamespaceSummary,
    WorkloadRequestSummary,
)
from .report import money, num, pct


SENSITIVE_KEYS = {
    "namespace": "namespace",
    "pod": "workload",
    "container": "container",
    "node": "node",
    "hostname": "node",
    "host": "node",
    "uuid": "gpu",
    "gpu_uuid": "gpu",
    "prometheus_url": "url",
    "url": "url",
    "endpoint": "url",
}
COMPOSITE_KEYS = {"gpu_id": "gpu"}
URL_PATTERN = re.compile(r"https?://[^\s)\"']+")


class RedactionMap:
    def __init__(self) -> None:
        self._aliases: dict[tuple[str, str], str] = {}
        self._text_aliases: dict[str, str] = {}
        self._counts: dict[str, int] = {}

    def alias(self, kind: str, value: object) -> str:
        original = str(value)
        if not should_redact(original):
            return original
        key = (kind, original)
        if key in self._aliases:
            return self._aliases[key]
        self._counts[kind] = self._counts.get(kind, 0) + 1
        if kind == "gpu":
            replacement = f"GPU-REDACTED-{self._counts[kind]:03d}"
        elif kind == "url":
            replacement = "https://redacted.example"
        else:
            replacement = f"{kind}-{self._counts[kind]:03d}"
        self._aliases[key] = replacement
        self._text_aliases.setdefault(original, replacement)
        return replacement

    def replace_known(self, text: str) -> str:
        redacted = text
        for original, replacement in sorted(
            self._text_aliases.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            if original:
                redacted = redacted.replace(original, replacement)
        return URL_PATTERN.sub("https://redacted.example", redacted)

    def to_dict(self) -> dict[str, str]:
        return dict(sorted(self._text_aliases.items()))


def should_redact(value: str) -> bool:
    return value.strip() not in {"", "unknown", "n/a", "None", "null"}


def should_redact_composite(value: str) -> bool:
    return should_redact(value) and len(value) <= 100 and not any(
        item.isspace() for item in value
    )


def load_json_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("report JSON must contain an object")
    return payload


def write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def redact_report(payload: dict[str, Any]) -> tuple[dict[str, Any], RedactionMap]:
    redactions = RedactionMap()
    collect_sensitive_values(payload, redactions)
    collect_composite_values(payload, redactions)
    redacted = redact_value(payload, redactions)
    if isinstance(redacted, dict):
        metadata = dict(redacted.get("redaction", {}))
        metadata.update(
            {
                "redacted": True,
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "strategy": "deterministic aliases scoped to this report",
            }
        )
        redacted["redaction"] = metadata
    return redacted, redactions


def collect_sensitive_values(value: Any, redactions: RedactionMap) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            kind = SENSITIVE_KEYS.get(str(key).lower())
            if kind and isinstance(item, str):
                redactions.alias(kind, item)
            collect_sensitive_values(item, redactions)
    elif isinstance(value, list):
        for item in value:
            collect_sensitive_values(item, redactions)


def collect_composite_values(value: Any, redactions: RedactionMap) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            kind = COMPOSITE_KEYS.get(str(key).lower())
            if kind and isinstance(item, str) and should_redact_composite(item):
                replaced = redactions.replace_known(item)
                if replaced == item:
                    redactions.alias(kind, item)
            collect_composite_values(item, redactions)
    elif isinstance(value, list):
        for item in value:
            collect_composite_values(item, redactions)


def redact_value(value: Any, redactions: RedactionMap, key: str | None = None) -> Any:
    lowered_key = str(key).lower() if key else None
    kind = SENSITIVE_KEYS.get(lowered_key) if lowered_key else None
    composite_kind = COMPOSITE_KEYS.get(lowered_key) if lowered_key else None
    if isinstance(value, dict):
        return {
            item_key: redact_value(item_value, redactions, item_key)
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [redact_value(item, redactions, key) for item in value]
    if isinstance(value, str):
        if lowered_key == "target":
            return redactions.replace_known(value)
        if composite_kind:
            replaced = redactions.replace_known(value)
            if replaced != value:
                return replaced
            if not should_redact_composite(value):
                return value
            return redactions.alias(composite_kind, value)
        if kind:
            return redactions.alias(kind, value)
        return redactions.replace_known(value)
    return value


def is_audit_report(payload: dict[str, Any]) -> bool:
    required = {
        "generated_at",
        "language",
        "window_hours",
        "total_gpus",
        "fleet_avg_utilization",
        "total_idle_gpu_hours",
        "gpus",
        "namespaces",
    }
    return required.issubset(payload)


def audit_report_from_mapping(payload: dict[str, Any]) -> AuditReport:
    return AuditReport(
        generated_at=str(payload.get("generated_at", "")),
        language=str(payload.get("language", "en")),
        window_hours=float(payload.get("window_hours", 0.0) or 0.0),
        step=str(payload.get("step", "")),
        price_per_gpu_hour=float(payload.get("price_per_gpu_hour", 0.0) or 0.0),
        gpu_prices={
            str(key): float(value)
            for key, value in dict(payload.get("gpu_prices", {})).items()
        },
        total_gpus=int(payload.get("total_gpus", 0) or 0),
        total_requested_gpu_hours=float(
            payload.get("total_requested_gpu_hours", 0.0) or 0.0
        ),
        fleet_avg_utilization=float(
            payload.get("fleet_avg_utilization", 0.0) or 0.0
        ),
        total_idle_gpu_hours=float(payload.get("total_idle_gpu_hours", 0.0) or 0.0),
        estimated_idle_cost=float(payload.get("estimated_idle_cost", 0.0) or 0.0),
        estimated_request_cost=float(
            payload.get("estimated_request_cost", 0.0) or 0.0
        ),
        gpus=[GpuSummary(**item) for item in payload.get("gpus", [])],
        gpu_models=[
            GpuModelSummary(**item) for item in payload.get("gpu_models", [])
        ],
        namespaces=[
            NamespaceSummary(**item) for item in payload.get("namespaces", [])
        ],
        workload_requests=[
            WorkloadRequestSummary(**item)
            for item in payload.get("workload_requests", [])
        ],
        action_items=[ActionItem(**item) for item in payload.get("action_items", [])],
        recommendations=[str(item) for item in payload.get("recommendations", [])],
        telemetry_gaps=[str(item) for item in payload.get("telemetry_gaps", [])],
    )


def render_case_study(
    payload: dict[str, Any],
    *,
    title: str,
    cluster_name: str,
    language: str,
) -> str:
    report = audit_report_from_mapping(payload)
    if language == "zh":
        return render_case_study_zh(report, title=title, cluster_name=cluster_name)
    return render_case_study_en(report, title=title, cluster_name=cluster_name)


def render_case_study_en(
    report: AuditReport,
    *,
    title: str,
    cluster_name: str,
) -> str:
    top_namespaces = sorted(
        report.namespaces,
        key=lambda item: (item.estimated_over_request_cost, item.over_requested_gpu_hours),
        reverse=True,
    )[:5]
    top_idle = sorted(
        report.gpus,
        key=lambda item: (item.estimated_idle_cost, item.idle_hours),
        reverse=True,
    )[:5]
    lines = [
        f"# {title}",
        "",
        "This is an anonymized GPU fleet audit case study generated by `ai-gpu-lens`.",
        "",
        "## Scope",
        "",
        f"- Cluster: {cluster_name}",
        f"- Window: {num(report.window_hours)}h, step {report.step}",
        f"- GPUs observed: {report.total_gpus}",
        "",
        "## Findings",
        "",
        f"- Fleet average GPU utilization was {pct(report.fleet_avg_utilization)}.",
        f"- Idle GPU time was {num(report.total_idle_gpu_hours)} GPU hours, estimated at {money(report.estimated_idle_cost)}.",
        f"- Requested GPU time was {num(report.total_requested_gpu_hours)} GPU hours, estimated at {money(report.estimated_request_cost)}.",
        "",
        "## Top Over-Requested Namespaces",
        "",
        table(
            ["Namespace", "Requested GPU h", "Used GPU h eq.", "Over-requested h", "Estimated cost"],
            [
                [
                    item.namespace,
                    num(item.requested_gpu_hours),
                    num(item.utilized_gpu_hour_equivalent),
                    num(item.over_requested_gpu_hours),
                    money(item.estimated_over_request_cost),
                ]
                for item in top_namespaces
            ],
        ),
        "",
        "## Top Idle GPUs",
        "",
        table(
            ["Node", "GPU", "Model", "Namespace", "Workload", "Avg util", "Idle h", "Idle cost"],
            [
                [
                    item.node,
                    item.index,
                    item.model,
                    item.namespace,
                    item.pod,
                    pct(item.avg_utilization),
                    num(item.idle_hours),
                    money(item.estimated_idle_cost),
                ]
                for item in top_idle
                if item.idle_hours > 0
            ],
        ),
        "",
        "## Recommended Follow-Up",
        "",
    ]
    lines.extend(f"- {item.action}" for item in report.action_items[:5])
    if not report.action_items:
        lines.append("- Validate a longer audit window before changing capacity.")
    return "\n".join(lines) + "\n"


def render_case_study_zh(
    report: AuditReport,
    *,
    title: str,
    cluster_name: str,
) -> str:
    top_namespaces = sorted(
        report.namespaces,
        key=lambda item: (item.estimated_over_request_cost, item.over_requested_gpu_hours),
        reverse=True,
    )[:5]
    top_idle = sorted(
        report.gpus,
        key=lambda item: (item.estimated_idle_cost, item.idle_hours),
        reverse=True,
    )[:5]
    lines = [
        f"# {title}",
        "",
        "这是一份由 `ai-gpu-lens` 生成的脱敏 GPU 集群审计案例。",
        "",
        "## 范围",
        "",
        f"- 集群：{cluster_name}",
        f"- 窗口：{num(report.window_hours)} 小时，step {report.step}",
        f"- GPU 数量：{report.total_gpus}",
        "",
        "## 主要发现",
        "",
        f"- 集群平均 GPU 利用率为 {pct(report.fleet_avg_utilization)}。",
        f"- 空闲 GPU 时间为 {num(report.total_idle_gpu_hours)} GPU 小时，估算成本 {money(report.estimated_idle_cost)}。",
        f"- 已申请 GPU 时间为 {num(report.total_requested_gpu_hours)} GPU 小时，估算成本 {money(report.estimated_request_cost)}。",
        "",
        "## 过度申请 Namespace Top",
        "",
        table(
            ["Namespace", "申请 GPU h", "有效使用 GPU h", "过度申请 h", "估算成本"],
            [
                [
                    item.namespace,
                    num(item.requested_gpu_hours),
                    num(item.utilized_gpu_hour_equivalent),
                    num(item.over_requested_gpu_hours),
                    money(item.estimated_over_request_cost),
                ]
                for item in top_namespaces
            ],
        ),
        "",
        "## 空闲 GPU Top",
        "",
        table(
            ["Node", "GPU", "型号", "Namespace", "Workload", "平均利用率", "空闲 h", "空闲成本"],
            [
                [
                    item.node,
                    item.index,
                    item.model,
                    item.namespace,
                    item.pod,
                    pct(item.avg_utilization),
                    num(item.idle_hours),
                    money(item.estimated_idle_cost),
                ]
                for item in top_idle
                if item.idle_hours > 0
            ],
        ),
        "",
        "## 建议后续动作",
        "",
    ]
    lines.extend(f"- {item.action}" for item in report.action_items[:5])
    if not report.action_items:
        lines.append("- 在调整容量前，先用更长时间窗口复核。")
    return "\n".join(lines) + "\n"


def table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        rows = [["n/a"] + [""] * (len(headers) - 1)]
    lines = [
        "| " + " | ".join(markdown_cell(item) for item in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        padded = row + [""] * (len(headers) - len(row))
        lines.append(
            "| " + " | ".join(markdown_cell(item) for item in padded[: len(headers)]) + " |"
        )
    return "\n".join(lines)


def markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def report_to_mapping(report: AuditReport) -> dict[str, Any]:
    return asdict(report)
