from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_gpu_lens.cli import archive_bundle, build_bundle_manifest, render_bundle_readme
from ai_gpu_lens.model import ActionItem, AuditReport


class BundleTest(unittest.TestCase):
    def test_manifest_and_archive_include_delivery_files(self) -> None:
        report = AuditReport(
            generated_at="2026-05-29T00:00:00+00:00",
            language="en",
            window_hours=24.0,
            step="5m",
            price_per_gpu_hour=2.5,
            gpu_prices={"default": 2.5},
            total_gpus=1,
            total_requested_gpu_hours=24.0,
            fleet_avg_utilization=12.5,
            total_idle_gpu_hours=4.0,
            estimated_idle_cost=10.0,
            estimated_request_cost=60.0,
            action_items=[
                ActionItem(
                    priority="High",
                    category="Right-sizing",
                    target="team/workload",
                    action="Reduce requested GPUs after owner review.",
                    estimated_window_savings=12.5,
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "bundle"
            output_dir.mkdir()
            (output_dir / "audit.html").write_text("<html></html>", encoding="utf-8")
            (output_dir / "audit.json").write_text("{}", encoding="utf-8")
            (output_dir / "audit.md").write_text("# audit", encoding="utf-8")
            manifest = build_bundle_manifest(
                "bundle",
                output_dir,
                report,
                source="file",
                doctor_included=False,
            )
            (output_dir / "manifest.json").write_text("{}", encoding="utf-8")
            (output_dir / "README.md").write_text(
                render_bundle_readme("bundle", report, manifest),
                encoding="utf-8",
            )
            archive_path = Path(tmp) / "bundle.zip"
            archive_bundle(output_dir, archive_path)

            self.assertIn("audit.html", manifest["files"])
            self.assertIn("manifest.json", manifest["files"])
            self.assertIn("README.md", manifest["files"])
            self.assertIn("Reduce requested GPUs", (output_dir / "README.md").read_text())
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(
                    sorted(archive.namelist()),
                    ["README.md", "audit.html", "audit.json", "audit.md", "manifest.json"],
                )


if __name__ == "__main__":
    unittest.main()
