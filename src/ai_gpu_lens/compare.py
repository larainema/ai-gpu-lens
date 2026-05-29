from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any


@dataclass
class MetricChange:
    name: str
    before: float
    after: float
    delta: float
    change_percent: float | None = None


@dataclass
class EntityChange:
    target: str
    before_hours: float
    after_hours: float
    delta_hours: float
    saved_hours: float
    before_cost: float
    after_cost: float
    delta_cost: float
    saved_cost: float


@dataclass
class ComparisonReport:
    generated_at: str
    language: str
    before_generated_at: str
    after_generated_at: str
    before_window_hours: float
    after_window_hours: float
    metrics: list[MetricChange] = field(default_factory=list)
    improved_namespaces: list[EntityChange] = field(default_factory=list)
    regressed_namespaces: list[EntityChange] = field(default_factory=list)
    improved_workloads: list[EntityChange] = field(default_factory=list)
    regressed_workloads: list[EntityChange] = field(default_factory=list)
    resolved_telemetry_gaps: list[str] = field(default_factory=list)
    new_telemetry_gaps: list[str] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)


def load_audit_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("audit report JSON must contain an object")
    return payload


def build_comparison(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    language: str = "en",
) -> ComparisonReport:
    language = "zh" if language == "zh" else "en"
    metrics = [
        metric_change("total_gpus", before, after),
        metric_change("fleet_avg_utilization", before, after),
        metric_change("total_idle_gpu_hours", before, after),
        metric_change("estimated_idle_cost", before, after),
        metric_change("total_requested_gpu_hours", before, after),
        metric_change("estimated_request_cost", before, after),
        MetricChange(
            name="over_requested_gpu_hours",
            before=total_over_requested_hours(before),
            after=total_over_requested_hours(after),
            delta=total_over_requested_hours(after)
            - total_over_requested_hours(before),
            change_percent=percent_change(
                total_over_requested_hours(before),
                total_over_requested_hours(after),
            ),
        ),
        MetricChange(
            name="estimated_over_request_cost",
            before=total_over_requested_cost(before),
            after=total_over_requested_cost(after),
            delta=total_over_requested_cost(after)
            - total_over_requested_cost(before),
            change_percent=percent_change(
                total_over_requested_cost(before),
                total_over_requested_cost(after),
            ),
        ),
    ]

    namespace_changes = compare_entities(
        before.get("namespaces", []),
        after.get("namespaces", []),
        key_fields=("namespace",),
    )
    workload_changes = compare_entities(
        before.get("workload_requests", []),
        after.get("workload_requests", []),
        key_fields=("namespace", "pod"),
    )
    before_gaps = set(str(item) for item in before.get("telemetry_gaps", []))
    after_gaps = set(str(item) for item in after.get("telemetry_gaps", []))
    summary = build_summary(metrics, language=language)

    return ComparisonReport(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        language=language,
        before_generated_at=str(before.get("generated_at", "unknown")),
        after_generated_at=str(after.get("generated_at", "unknown")),
        before_window_hours=float(before.get("window_hours", 0.0) or 0.0),
        after_window_hours=float(after.get("window_hours", 0.0) or 0.0),
        metrics=metrics,
        improved_namespaces=[
            item for item in namespace_changes if item.saved_cost > 0 or item.saved_hours > 0
        ][:10],
        regressed_namespaces=[
            item for item in namespace_changes if item.delta_cost > 0 or item.delta_hours > 0
        ][:10],
        improved_workloads=[
            item for item in workload_changes if item.saved_cost > 0 or item.saved_hours > 0
        ][:10],
        regressed_workloads=[
            item for item in workload_changes if item.delta_cost > 0 or item.delta_hours > 0
        ][:10],
        resolved_telemetry_gaps=sorted(before_gaps - after_gaps),
        new_telemetry_gaps=sorted(after_gaps - before_gaps),
        summary=summary,
    )


def metric_change(
    name: str,
    before: dict[str, Any],
    after: dict[str, Any],
) -> MetricChange:
    before_value = float(before.get(name, 0.0) or 0.0)
    after_value = float(after.get(name, 0.0) or 0.0)
    return MetricChange(
        name=name,
        before=before_value,
        after=after_value,
        delta=after_value - before_value,
        change_percent=percent_change(before_value, after_value),
    )


def percent_change(before: float, after: float) -> float | None:
    if before == 0:
        return None
    return ((after - before) / before) * 100.0


def total_over_requested_hours(report: dict[str, Any]) -> float:
    return sum(
        float(item.get("over_requested_gpu_hours", 0.0) or 0.0)
        for item in report.get("namespaces", [])
    )


def total_over_requested_cost(report: dict[str, Any]) -> float:
    return sum(
        float(item.get("estimated_over_request_cost", 0.0) or 0.0)
        for item in report.get("namespaces", [])
    )


def compare_entities(
    before_items: list[dict[str, Any]],
    after_items: list[dict[str, Any]],
    *,
    key_fields: tuple[str, ...],
) -> list[EntityChange]:
    before_by_key = {entity_key(item, key_fields): item for item in before_items}
    after_by_key = {entity_key(item, key_fields): item for item in after_items}
    changes = []
    for key in sorted(set(before_by_key) | set(after_by_key)):
        before = before_by_key.get(key, {})
        after = after_by_key.get(key, {})
        before_hours = float(before.get("over_requested_gpu_hours", 0.0) or 0.0)
        after_hours = float(after.get("over_requested_gpu_hours", 0.0) or 0.0)
        before_cost = float(before.get("estimated_over_request_cost", 0.0) or 0.0)
        after_cost = float(after.get("estimated_over_request_cost", 0.0) or 0.0)
        changes.append(
            EntityChange(
                target=key,
                before_hours=before_hours,
                after_hours=after_hours,
                delta_hours=after_hours - before_hours,
                saved_hours=before_hours - after_hours,
                before_cost=before_cost,
                after_cost=after_cost,
                delta_cost=after_cost - before_cost,
                saved_cost=before_cost - after_cost,
            )
        )
    changes.sort(key=lambda item: max(item.saved_cost, item.delta_cost), reverse=True)
    return changes


def entity_key(item: dict[str, Any], key_fields: tuple[str, ...]) -> str:
    return "/".join(str(item.get(field, "unknown")) for field in key_fields)


def build_summary(metrics: list[MetricChange], *, language: str) -> list[str]:
    metric_by_name = {item.name: item for item in metrics}
    idle_cost = metric_by_name["estimated_idle_cost"]
    idle_hours = metric_by_name["total_idle_gpu_hours"]
    over_hours = metric_by_name["over_requested_gpu_hours"]
    util = metric_by_name["fleet_avg_utilization"]
    if language == "zh":
        return [
            f"空闲成本变化 {money_delta(idle_cost.delta)}。",
            f"空闲 GPU 小时变化 {signed_num(idle_hours.delta)}。",
            f"过度申请 GPU 小时变化 {signed_num(over_hours.delta)}。",
            f"集群平均利用率变化 {signed_pct_points(util.delta)}。",
        ]
    return [
        f"Idle cost changed by {money_delta(idle_cost.delta)}.",
        f"Idle GPU hours changed by {signed_num(idle_hours.delta)}.",
        f"Over-requested GPU hours changed by {signed_num(over_hours.delta)}.",
        f"Fleet average utilization changed by {signed_pct_points(util.delta)}.",
    ]


def write_comparison_json(report: ComparisonReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2) + "\n", encoding="utf-8")


def write_comparison_html(report: ComparisonReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_comparison_html(report), encoding="utf-8")


def write_comparison_markdown(report: ComparisonReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_comparison_markdown(report), encoding="utf-8")


def render_comparison_html(report: ComparisonReport) -> str:
    labels = labels_for(report.language)
    summary = "\n".join(f"<li>{escape(item)}</li>" for item in report.summary)
    metric_rows = "\n".join(
        f"""
        <tr>
          <td>{escape(labels.get(metric.name, metric.name))}</td>
          <td>{format_metric(metric.name, metric.before)}</td>
          <td>{format_metric(metric.name, metric.after)}</td>
          <td>{format_delta(metric.name, metric.delta)}</td>
          <td>{format_percent(metric.change_percent)}</td>
        </tr>
        """
        for metric in report.metrics
    )
    return f"""<!doctype html>
<html lang="{escape('zh-Hans' if report.language == 'zh' else 'en')}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(labels['title'])}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8f4;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #5f6c72;
      --line: #dbe3df;
      --soft: #e9f3ef;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      gap: 20px;
      align-items: end;
      margin-bottom: 24px;
    }}
    h1 {{ margin: 0 0 6px; font-size: 32px; line-height: 1.1; }}
    h2 {{ margin: 30px 0 12px; font-size: 18px; }}
    .meta, .subtitle {{ color: var(--muted); }}
    .panel, table {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .panel {{ padding: 16px 18px; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
    }}
    th {{ background: var(--soft); font-size: 12px; text-transform: uppercase; }}
    tr:last-child td {{ border-bottom: 0; }}
    ul {{ margin: 0; padding-left: 18px; }}
    li + li {{ margin-top: 8px; }}
    .table-wrap {{ overflow-x: auto; border-radius: 8px; }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>{escape(labels['title'])}</h1>
        <div class="subtitle">{escape(labels['subtitle'])}</div>
      </div>
      <div class="meta">
        {escape(labels['generated'])} {escape(report.generated_at)}<br>
        {escape(labels['before'])}: {escape(report.before_generated_at)}
        ({num(report.before_window_hours)}h)<br>
        {escape(labels['after'])}: {escape(report.after_generated_at)}
        ({num(report.after_window_hours)}h)
      </div>
    </header>
    <h2>{escape(labels['summary'])}</h2>
    <section class="panel"><ul>{summary}</ul></section>
    <h2>{escape(labels['metrics'])}</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{escape(labels['metric'])}</th>
            <th>{escape(labels['before'])}</th>
            <th>{escape(labels['after'])}</th>
            <th>{escape(labels['delta'])}</th>
            <th>{escape(labels['change'])}</th>
          </tr>
        </thead>
        <tbody>{metric_rows}</tbody>
      </table>
    </div>
    {entity_section(labels, 'improved_namespaces', report.improved_namespaces)}
    {entity_section(labels, 'regressed_namespaces', report.regressed_namespaces, regressed=True)}
    {entity_section(labels, 'improved_workloads', report.improved_workloads)}
    {entity_section(labels, 'regressed_workloads', report.regressed_workloads, regressed=True)}
    {gap_section(labels['resolved_gaps'], report.resolved_telemetry_gaps)}
    {gap_section(labels['new_gaps'], report.new_telemetry_gaps)}
  </main>
</body>
</html>
"""


def entity_section(
    labels: dict[str, str],
    title_key: str,
    items: list[EntityChange],
    *,
    regressed: bool = False,
) -> str:
    rows = "\n".join(
        f"""
        <tr>
          <td>{escape(item.target)}</td>
          <td>{num(item.before_hours)}</td>
          <td>{num(item.after_hours)}</td>
          <td>{num(item.delta_hours)}</td>
          <td>{money(item.before_cost)}</td>
          <td>{money(item.after_cost)}</td>
          <td>{money(item.delta_cost if regressed else item.saved_cost)}</td>
        </tr>
        """
        for item in items
    )
    if not rows:
        rows = '<tr><td colspan="7">n/a</td></tr>'
    title = labels[title_key]
    final_header = labels["regressed_cost" if regressed else "saved_cost"]
    return f"""
    <h2>{escape(title)}</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{escape(labels['target'])}</th>
            <th>{escape(labels['before_hours'])}</th>
            <th>{escape(labels['after_hours'])}</th>
            <th>{escape(labels['delta_hours'])}</th>
            <th>{escape(labels['before_cost'])}</th>
            <th>{escape(labels['after_cost'])}</th>
            <th>{escape(final_header)}</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    """


def gap_section(title: str, gaps: list[str]) -> str:
    rows = "\n".join(f"<li>{escape(item)}</li>" for item in gaps)
    if not rows:
        rows = "<li>n/a</li>"
    return f"""
    <h2>{escape(title)}</h2>
    <section class="panel"><ul>{rows}</ul></section>
    """


def render_comparison_markdown(report: ComparisonReport) -> str:
    labels = labels_for(report.language)
    lines = [
        f"# {labels['title']}",
        "",
        labels["subtitle"],
        "",
        f"- {labels['generated']}: {report.generated_at}",
        f"- {labels['before']}: {report.before_generated_at}",
        f"- {labels['after']}: {report.after_generated_at}",
        "",
        f"## {labels['summary']}",
        "",
    ]
    lines.extend(f"- {item}" for item in report.summary)
    lines.extend(
        [
            "",
            f"## {labels['metrics']}",
            "",
            markdown_table(
                [labels["metric"], labels["before"], labels["after"], labels["delta"], labels["change"]],
                [
                    [
                        labels.get(metric.name, metric.name),
                        format_metric(metric.name, metric.before),
                        format_metric(metric.name, metric.after),
                        format_delta(metric.name, metric.delta),
                        format_percent(metric.change_percent),
                    ]
                    for metric in report.metrics
                ],
            ),
            "",
            entity_markdown(labels, "improved_namespaces", report.improved_namespaces),
            "",
            entity_markdown(
                labels,
                "regressed_namespaces",
                report.regressed_namespaces,
                regressed=True,
            ),
            "",
            entity_markdown(labels, "improved_workloads", report.improved_workloads),
            "",
            entity_markdown(
                labels,
                "regressed_workloads",
                report.regressed_workloads,
                regressed=True,
            ),
            "",
            gap_markdown(labels["resolved_gaps"], report.resolved_telemetry_gaps),
            "",
            gap_markdown(labels["new_gaps"], report.new_telemetry_gaps),
            "",
        ]
    )
    return "\n".join(lines)


def entity_markdown(
    labels: dict[str, str],
    title_key: str,
    items: list[EntityChange],
    *,
    regressed: bool = False,
) -> str:
    final_header = labels["regressed_cost" if regressed else "saved_cost"]
    return "\n".join(
        [
            f"## {labels[title_key]}",
            "",
            markdown_table(
                [
                    labels["target"],
                    labels["before_hours"],
                    labels["after_hours"],
                    labels["delta_hours"],
                    labels["before_cost"],
                    labels["after_cost"],
                    final_header,
                ],
                [
                    [
                        item.target,
                        num(item.before_hours),
                        num(item.after_hours),
                        num(item.delta_hours),
                        money(item.before_cost),
                        money(item.after_cost),
                        money(item.delta_cost if regressed else item.saved_cost),
                    ]
                    for item in items
                ],
            ),
        ]
    )


def gap_markdown(title: str, gaps: list[str]) -> str:
    values = gaps or ["n/a"]
    return "\n".join([f"## {title}", "", *[f"- {item}" for item in values]])


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        rows = [["n/a"] + [""] * (len(headers) - 1)]
    table = [
        "| " + " | ".join(markdown_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        padded = row + [""] * (len(headers) - len(row))
        table.append(
            "| " + " | ".join(markdown_cell(cell) for cell in padded[: len(headers)]) + " |"
        )
    return "\n".join(table)


def markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def labels_for(language: str) -> dict[str, str]:
    if language == "zh":
        return {
            "title": "ai-gpu-lens 对比报告",
            "subtitle": "GPU 审计前后变化、节省和回归",
            "generated": "生成时间",
            "before": "之前",
            "after": "之后",
            "summary": "摘要",
            "metrics": "核心指标",
            "metric": "指标",
            "delta": "变化",
            "change": "变化率",
            "target": "对象",
            "before_hours": "之前小时",
            "after_hours": "之后小时",
            "delta_hours": "小时变化",
            "before_cost": "之前成本",
            "after_cost": "之后成本",
            "saved_cost": "节省成本",
            "regressed_cost": "新增成本",
            "improved_namespaces": "改善命名空间 Top",
            "regressed_namespaces": "恶化命名空间 Top",
            "improved_workloads": "改善 Workload Top",
            "regressed_workloads": "恶化 Workload Top",
            "resolved_gaps": "已解决遥测缺口",
            "new_gaps": "新增遥测缺口",
            "total_gpus": "GPU 数量",
            "fleet_avg_utilization": "集群平均利用率",
            "total_idle_gpu_hours": "空闲 GPU 小时",
            "estimated_idle_cost": "空闲成本",
            "total_requested_gpu_hours": "已申请 GPU 小时",
            "estimated_request_cost": "申请成本",
            "over_requested_gpu_hours": "过度申请 GPU 小时",
            "estimated_over_request_cost": "过度申请成本",
        }
    return {
        "title": "ai-gpu-lens comparison report",
        "subtitle": "GPU audit deltas, savings, and regressions",
        "generated": "Generated",
        "before": "Before",
        "after": "After",
        "summary": "Summary",
        "metrics": "Core Metrics",
        "metric": "Metric",
        "delta": "Delta",
        "change": "Change",
        "target": "Target",
        "before_hours": "Before hours",
        "after_hours": "After hours",
        "delta_hours": "Delta hours",
        "before_cost": "Before cost",
        "after_cost": "After cost",
        "saved_cost": "Saved cost",
        "regressed_cost": "Regressed cost",
        "improved_namespaces": "Top Improved Namespaces",
        "regressed_namespaces": "Top Regressed Namespaces",
        "improved_workloads": "Top Improved Workloads",
        "regressed_workloads": "Top Regressed Workloads",
        "resolved_gaps": "Resolved Telemetry Gaps",
        "new_gaps": "New Telemetry Gaps",
        "total_gpus": "GPUs",
        "fleet_avg_utilization": "Fleet avg util",
        "total_idle_gpu_hours": "Idle GPU hours",
        "estimated_idle_cost": "Idle cost",
        "total_requested_gpu_hours": "Requested GPU hours",
        "estimated_request_cost": "Requested cost",
        "over_requested_gpu_hours": "Over-requested GPU hours",
        "estimated_over_request_cost": "Over-requested cost",
    }


def format_metric(name: str, value: float) -> str:
    if "cost" in name:
        return money(value)
    if "utilization" in name:
        return pct(value)
    if name == "total_gpus":
        return f"{value:.0f}"
    return num(value)


def format_delta(name: str, value: float) -> str:
    if "cost" in name:
        return money_delta(value)
    if "utilization" in name:
        return signed_pct_points(value)
    if name == "total_gpus":
        return signed_num(value, digits=0)
    return signed_num(value)


def format_percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    return signed_num(value) + "%"


def num(value: float, *, digits: int = 2) -> str:
    return f"{value:,.{digits}f}"


def signed_num(value: float, *, digits: int = 2) -> str:
    return f"{value:+,.{digits}f}"


def pct(value: float) -> str:
    return f"{value:.1f}%"


def signed_pct_points(value: float) -> str:
    return f"{value:+.1f} pp"


def money(value: float) -> str:
    return f"${value:,.2f}"


def money_delta(value: float) -> str:
    return f"{value:+,.2f} USD"
