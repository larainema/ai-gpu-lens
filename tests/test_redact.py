from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_gpu_lens.redact import (
    audit_report_from_mapping,
    redact_report,
    render_case_study,
    write_json,
)


class RedactTest(unittest.TestCase):
    def test_redacts_sensitive_identifiers_and_embedded_text(self) -> None:
        redacted, redactions = redact_report(audit_payload())
        text = json.dumps(redacted, ensure_ascii=False)

        self.assertNotIn("prod-ns", text)
        self.assertNotIn("training-job-0", text)
        self.assertNotIn("gpu-node-a", text)
        self.assertNotIn("GPU-abc123", text)
        self.assertIn("namespace-001", text)
        self.assertIn("workload-001", text)
        self.assertIn("node-001", text)
        self.assertIn("GPU-REDACTED-001", text)
        self.assertIn("namespace-001/workload-001", text)
        self.assertTrue(redacted["redaction"]["redacted"])
        self.assertEqual(redactions.to_dict()["prod-ns"], "namespace-001")

    def test_renders_case_study_from_redacted_audit(self) -> None:
        redacted, _redactions = redact_report(audit_payload())
        report = audit_report_from_mapping(redacted)
        case_study = render_case_study(
            redacted,
            title="Public GPU Audit",
            cluster_name="demo-cluster",
            language="en",
        )

        self.assertEqual(report.gpus[0].node, "node-001")
        self.assertIn("# Public GPU Audit", case_study)
        self.assertIn("demo-cluster", case_study)
        self.assertIn("namespace-001", case_study)
        self.assertNotIn("prod-ns", case_study)

    def test_writes_redacted_json(self) -> None:
        redacted, _redactions = redact_report(audit_payload())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "redacted.json"
            write_json(redacted, path)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertTrue(payload["redaction"]["redacted"])


def audit_payload() -> dict[str, object]:
    return {
        "generated_at": "2026-05-30T00:00:00+00:00",
        "language": "en",
        "window_hours": 24.0,
        "step": "5m",
        "price_per_gpu_hour": 2.5,
        "gpu_prices": {"H100": 4.25},
        "total_gpus": 1,
        "total_requested_gpu_hours": 24.0,
        "fleet_avg_utilization": 12.5,
        "total_idle_gpu_hours": 12.0,
        "estimated_idle_cost": 30.0,
        "estimated_request_cost": 60.0,
        "gpus": [
            {
                "gpu_id": "gpu-node-a/GPU-abc123",
                "node": "gpu-node-a",
                "uuid": "GPU-abc123",
                "index": "0",
                "model": "NVIDIA H100 80GB HBM3",
                "namespace": "prod-ns",
                "pod": "training-job-0",
                "avg_utilization": 12.5,
                "max_utilization": 20.0,
                "active_ratio": 0.2,
                "idle_hours": 12.0,
                "observed_hours": 24.0,
                "avg_memory_percent": 45.0,
                "max_memory_percent": 50.0,
                "price_per_gpu_hour": 2.5,
                "estimated_idle_cost": 30.0,
                "source_series_count": 1,
                "samples": 289,
            }
        ],
        "gpu_models": [
            {
                "model": "NVIDIA H100 80GB HBM3",
                "count": 1,
                "avg_utilization": 12.5,
                "total_idle_gpu_hours": 12.0,
                "estimated_idle_cost": 30.0,
                "price_per_gpu_hour": 2.5,
            }
        ],
        "namespaces": [
            {
                "namespace": "prod-ns",
                "utilized_gpu_hour_equivalent": 3.0,
                "requested_gpu_hours": 24.0,
                "over_requested_gpu_hours": 21.0,
                "estimated_request_cost": 60.0,
                "estimated_over_request_cost": 52.5,
                "series_count": 1,
                "avg_utilization": 12.5,
            }
        ],
        "workload_requests": [
            {
                "namespace": "prod-ns",
                "pod": "training-job-0",
                "avg_requested_gpus": 1.0,
                "requested_gpu_hours": 24.0,
                "estimated_request_cost": 60.0,
                "utilized_gpu_hour_equivalent": 3.0,
                "over_requested_gpu_hours": 21.0,
                "estimated_over_request_cost": 52.5,
                "samples": 289,
            }
        ],
        "action_items": [
            {
                "priority": "High",
                "category": "Right-sizing",
                "target": "prod-ns/training-job-0",
                "action": "Review prod-ns/training-job-0 before resizing.",
                "estimated_window_savings": 52.5,
            }
        ],
        "recommendations": ["Review prod-ns/training-job-0."],
        "telemetry_gaps": [],
    }


if __name__ == "__main__":
    unittest.main()
