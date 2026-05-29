from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_gpu_lens.compare import (
    build_comparison,
    render_comparison_html,
    render_comparison_markdown,
    write_comparison_json,
)


class CompareTest(unittest.TestCase):
    def test_builds_savings_and_regressions(self) -> None:
        before = audit_payload(
            idle_cost=100.0,
            idle_hours=40.0,
            util=25.0,
            namespaces=[
                namespace("team-a", 20.0, 50.0),
                namespace("team-b", 5.0, 12.5),
            ],
            workloads=[
                workload("team-a", "job-a", 20.0, 50.0),
                workload("team-b", "job-b", 5.0, 12.5),
            ],
            gaps=["missing labels"],
        )
        after = audit_payload(
            idle_cost=60.0,
            idle_hours=20.0,
            util=40.0,
            namespaces=[
                namespace("team-a", 5.0, 12.5),
                namespace("team-b", 8.0, 20.0),
            ],
            workloads=[
                workload("team-a", "job-a", 5.0, 12.5),
                workload("team-b", "job-b", 8.0, 20.0),
            ],
            gaps=[],
        )

        report = build_comparison(before, after, language="en")

        self.assertEqual(report.improved_namespaces[0].target, "team-a")
        self.assertAlmostEqual(report.improved_namespaces[0].saved_cost, 37.5)
        self.assertEqual(report.regressed_namespaces[0].target, "team-b")
        self.assertAlmostEqual(report.regressed_namespaces[0].delta_cost, 7.5)
        self.assertEqual(report.resolved_telemetry_gaps, ["missing labels"])
        self.assertIn("Idle cost changed by -40.00 USD.", report.summary)

    def test_renders_outputs(self) -> None:
        report = build_comparison(
            audit_payload(idle_cost=10.0, idle_hours=4.0, util=10.0),
            audit_payload(idle_cost=5.0, idle_hours=2.0, util=20.0),
            language="zh",
        )
        html = render_comparison_html(report)
        markdown = render_comparison_markdown(report)

        self.assertIn("ai-gpu-lens 对比报告", html)
        self.assertIn("节省成本", html)
        self.assertIn("# ai-gpu-lens 对比报告", markdown)
        self.assertIn("节省成本", markdown)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "comparison.json"
            write_comparison_json(report, path)
            self.assertIn("metrics", path.read_text(encoding="utf-8"))


def audit_payload(
    *,
    idle_cost: float,
    idle_hours: float,
    util: float,
    namespaces: list[dict[str, object]] | None = None,
    workloads: list[dict[str, object]] | None = None,
    gaps: list[str] | None = None,
) -> dict[str, object]:
    return {
        "generated_at": "2026-05-29T00:00:00+00:00",
        "language": "en",
        "window_hours": 24.0,
        "fleet_avg_utilization": util,
        "total_gpus": 8,
        "total_idle_gpu_hours": idle_hours,
        "estimated_idle_cost": idle_cost,
        "total_requested_gpu_hours": 100.0,
        "estimated_request_cost": 250.0,
        "namespaces": namespaces or [],
        "workload_requests": workloads or [],
        "telemetry_gaps": gaps or [],
    }


def namespace(name: str, hours: float, cost: float) -> dict[str, object]:
    return {
        "namespace": name,
        "over_requested_gpu_hours": hours,
        "estimated_over_request_cost": cost,
    }


def workload(
    namespace_name: str,
    pod: str,
    hours: float,
    cost: float,
) -> dict[str, object]:
    return {
        "namespace": namespace_name,
        "pod": pod,
        "over_requested_gpu_hours": hours,
        "estimated_over_request_cost": cost,
    }


if __name__ == "__main__":
    unittest.main()
