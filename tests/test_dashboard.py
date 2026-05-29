from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_gpu_lens.dashboard import build_grafana_dashboard, write_dashboard_json


class DashboardTest(unittest.TestCase):
    def test_builds_importable_dashboard(self) -> None:
        dashboard = build_grafana_dashboard()

        self.assertEqual(dashboard["uid"], "ai-gpu-lens")
        self.assertEqual(dashboard["__inputs"][0]["pluginId"], "prometheus")
        self.assertGreaterEqual(len(dashboard["panels"]), 9)
        panel_titles = {panel["title"] for panel in dashboard["panels"]}
        self.assertIn("Fleet GPU utilization", panel_titles)
        self.assertIn("Requested GPUs by namespace", panel_titles)

    def test_custom_datasource_uid_omits_import_input(self) -> None:
        dashboard = build_grafana_dashboard(
            datasource_uid="prometheus",
            kube_gpu_request_query=None,
        )

        self.assertEqual(dashboard["__inputs"], [])
        self.assertEqual(dashboard["panels"][0]["datasource"]["uid"], "prometheus")
        panel_titles = {panel["title"] for panel in dashboard["panels"]}
        self.assertNotIn("Requested GPUs by namespace", panel_titles)

    def test_writes_dashboard_json(self) -> None:
        dashboard = build_grafana_dashboard(title="GPU Lens")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dashboard.json"
            write_dashboard_json(dashboard, path)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["title"], "GPU Lens")
        self.assertEqual(payload["panels"][0]["targets"][0]["refId"], "A")


if __name__ == "__main__":
    unittest.main()
