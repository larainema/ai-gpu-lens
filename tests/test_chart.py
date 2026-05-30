from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_gpu_lens.config import load_config


ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "charts" / "ai-gpu-lens"


class ChartTest(unittest.TestCase):
    def test_chart_files_exist(self) -> None:
        expected = [
            "Chart.yaml",
            "values.yaml",
            "templates/configmap.yaml",
            "templates/cronjob.yaml",
            "templates/pvc.yaml",
            "templates/secret.yaml",
            "templates/serviceaccount.yaml",
        ]

        for relative_path in expected:
            self.assertTrue((CHART / relative_path).exists(), relative_path)

    def test_chart_uses_read_only_defaults(self) -> None:
        cronjob = (CHART / "templates" / "cronjob.yaml").read_text(encoding="utf-8")
        service_account = (
            CHART / "templates" / "serviceaccount.yaml"
        ).read_text(encoding="utf-8")

        self.assertIn("automountServiceAccountToken: false", cronjob)
        self.assertIn("readOnlyRootFilesystem: true", (CHART / "values.yaml").read_text())
        self.assertIn("automountServiceAccountToken: false", service_account)
        self.assertIn("args:", cronjob)
        self.assertIn("- bundle", cronjob)

    def test_example_values_parse_with_builtin_config_loader(self) -> None:
        values = load_config(ROOT / "examples" / "helm-values.yaml")

        self.assertEqual(
            values["config"]["prometheusUrl"],
            "https://grafana.example.com/api/datasources/proxy/uid/prometheus",
        )
        self.assertEqual(
            values["auth"]["bearerToken"]["existingSecret"],
            "grafana-viewer-token",
        )


if __name__ == "__main__":
    unittest.main()
