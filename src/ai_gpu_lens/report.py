from __future__ import annotations

import json
from dataclasses import asdict
from html import escape
from pathlib import Path
from typing import Any

from .i18n import t
from .model import AuditReport


def write_json_report(report: AuditReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(asdict(report), stream, indent=2)
        stream.write("\n")


def write_html_report(report: AuditReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(report), encoding="utf-8")


def write_markdown_report(report: AuditReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(report), encoding="utf-8")


def render_html(report: AuditReport) -> str:
    language = report.language
    cards = [
        (t(language, "gpus"), f"{report.total_gpus}"),
        (t(language, "fleet_avg_util"), pct(report.fleet_avg_utilization)),
        (t(language, "idle_gpu_hours"), num(report.total_idle_gpu_hours)),
        (t(language, "idle_cost"), money(report.estimated_idle_cost)),
        (t(language, "requested_gpu_hours"), num(report.total_requested_gpu_hours)),
        (t(language, "requested_cost"), money(report.estimated_request_cost)),
    ]
    card_html = "\n".join(
        f"""
        <section class="metric-card">
          <div class="metric-label">{escape(label)}</div>
          <div class="metric-value">{escape(value)}</div>
        </section>
        """
        for label, value in cards
    )
    executive_summary = "\n".join(
        f"<li>{escape(item)}</li>" for item in executive_summary_lines(report)
    )
    action_rows = "\n".join(
        f"""
        <tr>
          <td>{escape(item.priority)}</td>
          <td>{escape(item.category)}</td>
          <td>{escape(item.target)}</td>
          <td class="action-cell">{escape(item.action)}</td>
          <td>{money(item.estimated_window_savings)}</td>
        </tr>
        """
        for item in report.action_items
    )

    gpu_rows = "\n".join(
        f"""
        <tr>
          <td>{escape(gpu.node)}</td>
          <td>{escape(gpu.index)}</td>
          <td>{escape(gpu.model)}</td>
          <td>{escape(gpu.namespace)}</td>
          <td>{escape(gpu.pod)}</td>
          <td>{pct(gpu.avg_utilization)}</td>
          <td>{pct(gpu.max_utilization)}</td>
          <td>{pct(gpu.active_ratio * 100)}</td>
          <td>{num(gpu.idle_hours)}</td>
          <td>{optional_pct(gpu.avg_memory_percent, language)}</td>
          <td>{money(gpu.price_per_gpu_hour)}</td>
          <td>{money(gpu.estimated_idle_cost)}</td>
          <td>{gpu.source_series_count}</td>
        </tr>
        """
        for gpu in report.gpus
    )
    namespace_rows = "\n".join(
        f"""
        <tr>
          <td>{escape(ns.namespace)}</td>
          <td>{num(ns.utilized_gpu_hour_equivalent)}</td>
          <td>{num(ns.requested_gpu_hours)}</td>
          <td>{num(ns.over_requested_gpu_hours)}</td>
          <td>{money(ns.estimated_request_cost)}</td>
          <td>{money(ns.estimated_over_request_cost)}</td>
          <td>{pct(ns.avg_utilization)}</td>
          <td>{ns.series_count}</td>
        </tr>
        """
        for ns in report.namespaces
    )
    workload_request_rows = "\n".join(
        f"""
        <tr>
          <td>{escape(item.namespace)}</td>
          <td>{escape(item.pod)}</td>
          <td>{num(item.avg_requested_gpus)}</td>
          <td>{num(item.requested_gpu_hours)}</td>
          <td>{num(item.utilized_gpu_hour_equivalent)}</td>
          <td>{num(item.over_requested_gpu_hours)}</td>
          <td>{money(item.estimated_request_cost)}</td>
          <td>{money(item.estimated_over_request_cost)}</td>
        </tr>
        """
        for item in report.workload_requests
    )
    if not workload_request_rows:
        workload_request_rows = f"""
        <tr>
          <td colspan="8">{escape(t(language, "not_available"))}</td>
        </tr>
        """
    model_rows = "\n".join(
        f"""
        <tr>
          <td>{escape(item.model)}</td>
          <td>{item.count}</td>
          <td>{pct(item.avg_utilization)}</td>
          <td>{num(item.total_idle_gpu_hours)}</td>
          <td>{money(item.price_per_gpu_hour)}</td>
          <td>{money(item.estimated_idle_cost)}</td>
        </tr>
        """
        for item in report.gpu_models
    )
    idle_gpu_rows = "\n".join(
        f"""
        <tr>
          <td>{escape(gpu.node)}</td>
          <td>{escape(gpu.index)}</td>
          <td>{escape(gpu.model)}</td>
          <td>{escape(gpu.namespace)}</td>
          <td>{escape(gpu.pod)}</td>
          <td>{pct(gpu.avg_utilization)}</td>
          <td>{num(gpu.idle_hours)}</td>
          <td>{money(gpu.estimated_idle_cost)}</td>
        </tr>
        """
        for gpu in sorted(
            report.gpus,
            key=lambda item: (item.estimated_idle_cost, item.idle_hours),
            reverse=True,
        )[:10]
        if gpu.idle_hours > 0
    )
    over_namespace_rows = "\n".join(
        f"""
        <tr>
          <td>{escape(ns.namespace)}</td>
          <td>{num(ns.requested_gpu_hours)}</td>
          <td>{num(ns.utilized_gpu_hour_equivalent)}</td>
          <td>{num(ns.over_requested_gpu_hours)}</td>
          <td>{money(ns.estimated_over_request_cost)}</td>
        </tr>
        """
        for ns in sorted(
            report.namespaces,
            key=lambda item: (
                item.estimated_over_request_cost,
                item.over_requested_gpu_hours,
            ),
            reverse=True,
        )[:10]
        if ns.over_requested_gpu_hours > 0
    )
    over_workload_rows = "\n".join(
        f"""
        <tr>
          <td>{escape(item.namespace)}</td>
          <td>{escape(item.pod)}</td>
          <td>{num(item.requested_gpu_hours)}</td>
          <td>{num(item.utilized_gpu_hour_equivalent)}</td>
          <td>{num(item.over_requested_gpu_hours)}</td>
          <td>{money(item.estimated_over_request_cost)}</td>
        </tr>
        """
        for item in sorted(
            report.workload_requests,
            key=lambda item: (
                item.estimated_over_request_cost,
                item.over_requested_gpu_hours,
            ),
            reverse=True,
        )[:10]
        if item.over_requested_gpu_hours > 0
    )
    recommendations = "\n".join(
        f"<li>{escape(item)}</li>" for item in report.recommendations
    )
    telemetry_gaps = "\n".join(
        f"<li>{escape(item)}</li>" for item in report.telemetry_gaps
    )
    if not telemetry_gaps:
        telemetry_gaps = f"<li>{escape(t(language, 'no_telemetry_gaps'))}</li>"

    return f"""<!doctype html>
<html lang="{escape(t(language, "lang_html"))}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(t(language, "report_title"))}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8f4;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #5f6c72;
      --line: #dbe3df;
      --accent: #146c68;
      --accent-2: #b8472f;
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
    h1 {{
      margin: 0 0 6px;
      font-size: 32px;
      line-height: 1.1;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 30px 0 12px;
      font-size: 18px;
      letter-spacing: 0;
    }}
    .subtitle, .meta {{
      color: var(--muted);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 12px;
    }}
    .metric-card, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .metric-card {{
      padding: 16px;
    }}
    .metric-label {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }}
    .metric-value {{
      margin-top: 8px;
      font-size: 28px;
      line-height: 1;
      font-weight: 700;
    }}
    .panel {{
      padding: 16px 18px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
    }}
    th {{
      background: var(--soft);
      color: #233235;
      font-size: 12px;
      text-transform: uppercase;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    ul {{
      margin: 0;
      padding-left: 18px;
    }}
    li + li {{ margin-top: 8px; }}
    .table-wrap {{
      overflow-x: auto;
      border-radius: 8px;
    }}
    .accent {{ color: var(--accent); }}
    .action-cell {{ min-width: 320px; white-space: normal; }}
    @media (max-width: 760px) {{
      main {{ padding: 24px 12px 36px; }}
      header {{ display: block; }}
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      h1 {{ font-size: 26px; }}
      .metric-value {{ font-size: 23px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>{escape(t(language, "report_title"))}</h1>
        <div class="subtitle">{escape(t(language, "report_subtitle"))}</div>
      </div>
      <div class="meta">
        {escape(t(language, "generated"))} {escape(report.generated_at)}<br>
        {escape(t(language, "window"))} {num(report.window_hours)}h, step {escape(report.step)}
      </div>
    </header>

    <section class="grid">
      {card_html}
    </section>

    <h2>{escape(t(language, "executive_summary"))}</h2>
    <section class="panel">
      <ul>{executive_summary}</ul>
    </section>

    <h2>{escape(t(language, "action_items"))}</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{escape(t(language, "priority"))}</th>
            <th>{escape(t(language, "category"))}</th>
            <th>{escape(t(language, "target"))}</th>
            <th>{escape(t(language, "action"))}</th>
            <th>{escape(t(language, "estimated_savings"))}</th>
          </tr>
        </thead>
        <tbody>{action_rows}</tbody>
      </table>
    </div>

    <h2>{escape(t(language, "recommendations"))}</h2>
    <section class="panel">
      <ul>{recommendations}</ul>
    </section>

    <h2>{escape(t(language, "top_idle_gpus"))}</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{escape(t(language, "node"))}</th>
            <th>{escape(t(language, "gpu"))}</th>
            <th>{escape(t(language, "model"))}</th>
            <th>{escape(t(language, "namespace"))}</th>
            <th>{escape(t(language, "pod"))}</th>
            <th>{escape(t(language, "avg_util"))}</th>
            <th>{escape(t(language, "idle_hours"))}</th>
            <th>{escape(t(language, "idle_cost"))}</th>
          </tr>
        </thead>
        <tbody>{idle_gpu_rows}</tbody>
      </table>
    </div>

    <h2>{escape(t(language, "top_over_requested_namespaces"))}</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{escape(t(language, "namespace"))}</th>
            <th>{escape(t(language, "requested_gpu_hours"))}</th>
            <th>{escape(t(language, "utilized_gpu_hour_eq"))}</th>
            <th>{escape(t(language, "over_requested_gpu_hours"))}</th>
            <th>{escape(t(language, "over_requested_cost"))}</th>
          </tr>
        </thead>
        <tbody>{over_namespace_rows}</tbody>
      </table>
    </div>

    <h2>{escape(t(language, "top_over_requested_workloads"))}</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{escape(t(language, "namespace"))}</th>
            <th>{escape(t(language, "pod"))}</th>
            <th>{escape(t(language, "requested_gpu_hours"))}</th>
            <th>{escape(t(language, "utilized_gpu_hour_eq"))}</th>
            <th>{escape(t(language, "over_requested_gpu_hours"))}</th>
            <th>{escape(t(language, "over_requested_cost"))}</th>
          </tr>
        </thead>
        <tbody>{over_workload_rows}</tbody>
      </table>
    </div>

    <h2>{escape(t(language, "gpu_model_summary"))}</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{escape(t(language, "model"))}</th>
            <th>{escape(t(language, "gpus"))}</th>
            <th>{escape(t(language, "avg_util"))}</th>
            <th>{escape(t(language, "idle_gpu_hours"))}</th>
            <th>{escape(t(language, "price_per_hour"))}</th>
            <th>{escape(t(language, "idle_cost"))}</th>
          </tr>
        </thead>
        <tbody>{model_rows}</tbody>
      </table>
    </div>

    <h2>{escape(t(language, "namespace_attribution"))}</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{escape(t(language, "namespace"))}</th>
            <th>{escape(t(language, "utilized_gpu_hour_eq"))}</th>
            <th>{escape(t(language, "requested_gpu_hours"))}</th>
            <th>{escape(t(language, "over_requested_gpu_hours"))}</th>
            <th>{escape(t(language, "requested_cost"))}</th>
            <th>{escape(t(language, "over_requested_cost"))}</th>
            <th>{escape(t(language, "avg_util"))}</th>
            <th>{escape(t(language, "series"))}</th>
          </tr>
        </thead>
        <tbody>{namespace_rows}</tbody>
      </table>
    </div>

    <h2>{escape(t(language, "workload_requests"))}</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{escape(t(language, "namespace"))}</th>
            <th>{escape(t(language, "pod"))}</th>
            <th>{escape(t(language, "requested_gpus"))}</th>
            <th>{escape(t(language, "requested_gpu_hours"))}</th>
            <th>{escape(t(language, "utilized_gpu_hour_eq"))}</th>
            <th>{escape(t(language, "over_requested_gpu_hours"))}</th>
            <th>{escape(t(language, "requested_cost"))}</th>
            <th>{escape(t(language, "over_requested_cost"))}</th>
          </tr>
        </thead>
        <tbody>{workload_request_rows}</tbody>
      </table>
    </div>

    <h2>{escape(t(language, "gpu_detail"))}</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{escape(t(language, "node"))}</th>
            <th>{escape(t(language, "gpu"))}</th>
            <th>{escape(t(language, "model"))}</th>
            <th>{escape(t(language, "namespace"))}</th>
            <th>{escape(t(language, "pod"))}</th>
            <th>{escape(t(language, "avg_util"))}</th>
            <th>{escape(t(language, "max_util"))}</th>
            <th>{escape(t(language, "active_ratio"))}</th>
            <th>{escape(t(language, "idle_hours"))}</th>
            <th>{escape(t(language, "avg_mem"))}</th>
            <th>{escape(t(language, "price_per_hour"))}</th>
            <th>{escape(t(language, "idle_cost"))}</th>
            <th>{escape(t(language, "source_series"))}</th>
          </tr>
        </thead>
        <tbody>{gpu_rows}</tbody>
      </table>
    </div>

    <h2>{escape(t(language, "telemetry_gaps"))}</h2>
    <section class="panel">
      <ul>{telemetry_gaps}</ul>
    </section>
  </main>
</body>
</html>
"""


def render_markdown(report: AuditReport) -> str:
    language = report.language
    lines = [
        f"# {t(language, 'report_title')}",
        "",
        t(language, "report_subtitle"),
        "",
        f"- {t(language, 'generated')}: {report.generated_at}",
        f"- {t(language, 'window')}: {num(report.window_hours)}h, step {report.step}",
        f"- {t(language, 'gpus')}: {report.total_gpus}",
        f"- {t(language, 'fleet_avg_util')}: {pct(report.fleet_avg_utilization)}",
        f"- {t(language, 'idle_gpu_hours')}: {num(report.total_idle_gpu_hours)}",
        f"- {t(language, 'idle_cost')}: {money(report.estimated_idle_cost)}",
        f"- {t(language, 'requested_gpu_hours')}: {num(report.total_requested_gpu_hours)}",
        f"- {t(language, 'requested_cost')}: {money(report.estimated_request_cost)}",
        "",
        f"## {t(language, 'executive_summary')}",
        "",
    ]
    lines.extend(f"- {item}" for item in executive_summary_lines(report))
    lines.extend(
        [
            "",
            f"## {t(language, 'action_items')}",
            "",
            markdown_table(
                [
                    t(language, "priority"),
                    t(language, "category"),
                    t(language, "target"),
                    t(language, "action"),
                    t(language, "estimated_savings"),
                ],
                [
                    [
                        item.priority,
                        item.category,
                        item.target,
                        item.action,
                        money(item.estimated_window_savings),
                    ]
                    for item in report.action_items
                ],
            ),
            "",
            f"## {t(language, 'recommendations')}",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report.recommendations)
    lines.extend(
        [
            "",
            f"## {t(language, 'top_idle_gpus')}",
            "",
            markdown_table(
                [
                    t(language, "node"),
                    t(language, "gpu"),
                    t(language, "model"),
                    t(language, "namespace"),
                    t(language, "pod"),
                    t(language, "avg_util"),
                    t(language, "idle_hours"),
                    t(language, "idle_cost"),
                ],
                [
                    [
                        gpu.node,
                        gpu.index,
                        gpu.model,
                        gpu.namespace,
                        gpu.pod,
                        pct(gpu.avg_utilization),
                        num(gpu.idle_hours),
                        money(gpu.estimated_idle_cost),
                    ]
                    for gpu in sorted(
                        report.gpus,
                        key=lambda item: (item.estimated_idle_cost, item.idle_hours),
                        reverse=True,
                    )[:10]
                    if gpu.idle_hours > 0
                ],
            ),
            "",
            f"## {t(language, 'top_over_requested_namespaces')}",
            "",
            markdown_table(
                [
                    t(language, "namespace"),
                    t(language, "requested_gpu_hours"),
                    t(language, "utilized_gpu_hour_eq"),
                    t(language, "over_requested_gpu_hours"),
                    t(language, "over_requested_cost"),
                ],
                [
                    [
                        ns.namespace,
                        num(ns.requested_gpu_hours),
                        num(ns.utilized_gpu_hour_equivalent),
                        num(ns.over_requested_gpu_hours),
                        money(ns.estimated_over_request_cost),
                    ]
                    for ns in sorted(
                        report.namespaces,
                        key=lambda item: (
                            item.estimated_over_request_cost,
                            item.over_requested_gpu_hours,
                        ),
                        reverse=True,
                    )[:10]
                    if ns.over_requested_gpu_hours > 0
                ],
            ),
            "",
            f"## {t(language, 'top_over_requested_workloads')}",
            "",
            markdown_table(
                [
                    t(language, "namespace"),
                    t(language, "pod"),
                    t(language, "requested_gpu_hours"),
                    t(language, "utilized_gpu_hour_eq"),
                    t(language, "over_requested_gpu_hours"),
                    t(language, "over_requested_cost"),
                ],
                [
                    [
                        item.namespace,
                        item.pod,
                        num(item.requested_gpu_hours),
                        num(item.utilized_gpu_hour_equivalent),
                        num(item.over_requested_gpu_hours),
                        money(item.estimated_over_request_cost),
                    ]
                    for item in sorted(
                        report.workload_requests,
                        key=lambda item: (
                            item.estimated_over_request_cost,
                            item.over_requested_gpu_hours,
                        ),
                        reverse=True,
                    )[:10]
                    if item.over_requested_gpu_hours > 0
                ],
            ),
            "",
            f"## {t(language, 'gpu_model_summary')}",
            "",
            markdown_table(
                [
                    t(language, "model"),
                    t(language, "gpus"),
                    t(language, "avg_util"),
                    t(language, "idle_gpu_hours"),
                    t(language, "price_per_hour"),
                    t(language, "idle_cost"),
                ],
                [
                    [
                        item.model,
                        str(item.count),
                        pct(item.avg_utilization),
                        num(item.total_idle_gpu_hours),
                        money(item.price_per_gpu_hour),
                        money(item.estimated_idle_cost),
                    ]
                    for item in report.gpu_models
                ],
            ),
            "",
            f"## {t(language, 'namespace_attribution')}",
            "",
            markdown_table(
                [
                    t(language, "namespace"),
                    t(language, "utilized_gpu_hour_eq"),
                    t(language, "requested_gpu_hours"),
                    t(language, "over_requested_gpu_hours"),
                    t(language, "requested_cost"),
                    t(language, "over_requested_cost"),
                    t(language, "avg_util"),
                ],
                [
                    [
                        ns.namespace,
                        num(ns.utilized_gpu_hour_equivalent),
                        num(ns.requested_gpu_hours),
                        num(ns.over_requested_gpu_hours),
                        money(ns.estimated_request_cost),
                        money(ns.estimated_over_request_cost),
                        pct(ns.avg_utilization),
                    ]
                    for ns in report.namespaces
                ],
            ),
            "",
            f"## {t(language, 'workload_requests')}",
            "",
            markdown_table(
                [
                    t(language, "namespace"),
                    t(language, "pod"),
                    t(language, "requested_gpus"),
                    t(language, "requested_gpu_hours"),
                    t(language, "utilized_gpu_hour_eq"),
                    t(language, "over_requested_gpu_hours"),
                    t(language, "requested_cost"),
                    t(language, "over_requested_cost"),
                ],
                [
                    [
                        item.namespace,
                        item.pod,
                        num(item.avg_requested_gpus),
                        num(item.requested_gpu_hours),
                        num(item.utilized_gpu_hour_equivalent),
                        num(item.over_requested_gpu_hours),
                        money(item.estimated_request_cost),
                        money(item.estimated_over_request_cost),
                    ]
                    for item in report.workload_requests
                ],
            ),
            "",
            f"## {t(language, 'gpu_detail')}",
            "",
            markdown_table(
                [
                    t(language, "node"),
                    t(language, "gpu"),
                    t(language, "model"),
                    t(language, "namespace"),
                    t(language, "pod"),
                    t(language, "avg_util"),
                    t(language, "idle_hours"),
                    t(language, "price_per_hour"),
                    t(language, "idle_cost"),
                ],
                [
                    [
                        gpu.node,
                        gpu.index,
                        gpu.model,
                        gpu.namespace,
                        gpu.pod,
                        pct(gpu.avg_utilization),
                        num(gpu.idle_hours),
                        money(gpu.price_per_gpu_hour),
                        money(gpu.estimated_idle_cost),
                    ]
                    for gpu in report.gpus
                ],
            ),
            "",
            f"## {t(language, 'telemetry_gaps')}",
            "",
        ]
    )
    gaps = report.telemetry_gaps or [t(language, "no_telemetry_gaps")]
    lines.extend(f"- {item}" for item in gaps)
    lines.append("")
    return "\n".join(lines)


def executive_summary_lines(report: AuditReport) -> list[str]:
    language = report.language
    over_requested_hours = sum(
        item.over_requested_gpu_hours for item in report.workload_requests
    )
    if not over_requested_hours:
        over_requested_hours = sum(
            item.over_requested_gpu_hours for item in report.namespaces
        )
    return [
        t(
            language,
            "summary_utilization",
            count=report.total_gpus,
            util=pct(report.fleet_avg_utilization),
            hours=num(report.window_hours),
        ),
        t(
            language,
            "summary_idle_cost",
            cost=money(report.estimated_idle_cost),
        ),
        t(
            language,
            "summary_over_request",
            hours=num(over_requested_hours),
        ),
    ]


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


def pct(value: float) -> str:
    return f"{value:.1f}%"


def optional_pct(value: float | None, language: str = "en") -> str:
    if value is None:
        return t(language, "not_available")
    return pct(value)


def num(value: float) -> str:
    return f"{value:,.2f}"


def money(value: float) -> str:
    return f"${value:,.2f}"


def report_to_dict(report: AuditReport) -> dict[str, Any]:
    return asdict(report)
