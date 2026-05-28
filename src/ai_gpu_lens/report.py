from __future__ import annotations

import json
from dataclasses import asdict
from html import escape
from pathlib import Path
from typing import Any

from .model import AuditReport


def write_json_report(report: AuditReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(asdict(report), stream, indent=2)
        stream.write("\n")


def write_html_report(report: AuditReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(report), encoding="utf-8")


def render_html(report: AuditReport) -> str:
    cards = [
        ("GPUs", f"{report.total_gpus}"),
        ("Fleet avg util", pct(report.fleet_avg_utilization)),
        ("Idle GPU hours", num(report.total_idle_gpu_hours)),
        ("Idle cost", money(report.estimated_idle_cost)),
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
          <td>{optional_pct(gpu.avg_memory_percent)}</td>
          <td>{money(gpu.estimated_idle_cost)}</td>
        </tr>
        """
        for gpu in report.gpus
    )
    namespace_rows = "\n".join(
        f"""
        <tr>
          <td>{escape(ns.namespace)}</td>
          <td>{num(ns.utilized_gpu_hour_equivalent)}</td>
          <td>{pct(ns.avg_utilization)}</td>
          <td>{ns.series_count}</td>
        </tr>
        """
        for ns in report.namespaces
    )
    recommendations = "\n".join(
        f"<li>{escape(item)}</li>" for item in report.recommendations
    )
    telemetry_gaps = "\n".join(
        f"<li>{escape(item)}</li>" for item in report.telemetry_gaps
    )
    if not telemetry_gaps:
        telemetry_gaps = "<li>No major telemetry gaps detected.</li>"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ai-gpu-lens report</title>
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
      grid-template-columns: repeat(4, minmax(0, 1fr));
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
        <h1>ai-gpu-lens report</h1>
        <div class="subtitle">GPU utilization, idle hours, and cost attribution</div>
      </div>
      <div class="meta">
        Generated {escape(report.generated_at)}<br>
        Window {num(report.window_hours)}h, step {escape(report.step)}
      </div>
    </header>

    <section class="grid">
      {card_html}
    </section>

    <h2>Recommendations</h2>
    <section class="panel">
      <ul>{recommendations}</ul>
    </section>

    <h2>Namespace Attribution</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Namespace</th>
            <th>Utilized GPU-hour eq.</th>
            <th>Avg util</th>
            <th>Series</th>
          </tr>
        </thead>
        <tbody>{namespace_rows}</tbody>
      </table>
    </div>

    <h2>GPU Detail</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Node</th>
            <th>GPU</th>
            <th>Model</th>
            <th>Namespace</th>
            <th>Pod</th>
            <th>Avg util</th>
            <th>Max util</th>
            <th>Active ratio</th>
            <th>Idle hours</th>
            <th>Avg mem</th>
            <th>Idle cost</th>
          </tr>
        </thead>
        <tbody>{gpu_rows}</tbody>
      </table>
    </div>

    <h2>Telemetry Gaps</h2>
    <section class="panel">
      <ul>{telemetry_gaps}</ul>
    </section>
  </main>
</body>
</html>
"""


def pct(value: float) -> str:
    return f"{value:.1f}%"


def optional_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return pct(value)


def num(value: float) -> str:
    return f"{value:,.2f}"


def money(value: float) -> str:
    return f"${value:,.2f}"


def report_to_dict(report: AuditReport) -> dict[str, Any]:
    return asdict(report)
