from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_gpu_lens.model import ActionItem, AuditReport
from ai_gpu_lens.report import render_html, render_markdown


class ReportRenderingTest(unittest.TestCase):
    def test_action_confidence_and_evidence_are_rendered(self) -> None:
        report = AuditReport(
            generated_at="2026-05-30T00:00:00+00:00",
            language="en",
            window_hours=168.0,
            step="5m",
            price_per_gpu_hour=2.5,
            gpu_prices={"default": 2.5},
            total_gpus=1,
            total_requested_gpu_hours=24.0,
            fleet_avg_utilization=12.0,
            total_idle_gpu_hours=4.0,
            estimated_idle_cost=10.0,
            estimated_request_cost=60.0,
            action_items=[
                ActionItem(
                    priority="High",
                    category="Right-sizing",
                    target="team/workload",
                    action="Reduce GPU requests.",
                    estimated_window_savings=12.5,
                    confidence="High confidence",
                    evidence=["Requested 24 GPU hours.", "Used 4 GPU-hour equivalents."],
                    validation="Confirm with owner before changing requests.",
                )
            ],
        )

        html = render_html(report)
        markdown = render_markdown(report)

        self.assertIn("High confidence", html)
        self.assertIn("Requested 24 GPU hours.", html)
        self.assertIn("Confirm with owner", html)
        self.assertIn("## Action Evidence", markdown)
        self.assertIn("- Confidence: High confidence", markdown)
        self.assertIn("- Evidence: Requested 24 GPU hours.", markdown)
        self.assertIn("- Validation: Confirm with owner", markdown)


if __name__ == "__main__":
    unittest.main()
