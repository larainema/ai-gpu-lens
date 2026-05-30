from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_gpu_lens.cli import (
    archive_bundle,
    build_bundle_manifest,
    render_bundle_readme,
    write_public_bundle,
)
from ai_gpu_lens.model import ActionItem, AuditReport, GpuSummary, NamespaceSummary


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

    def test_public_bundle_redacts_sensitive_identifiers(self) -> None:
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
            gpus=[
                GpuSummary(
                    gpu_id="gpu-node-a/GPU-1234abcd",
                    node="gpu-node-a",
                    uuid="GPU-1234abcd",
                    index="0",
                    model="L40S",
                    namespace="team-prod",
                    pod="jupyter-alice",
                    avg_utilization=3.0,
                    max_utilization=8.0,
                    active_ratio=0.1,
                    idle_hours=4.0,
                    observed_hours=24.0,
                )
            ],
            namespaces=[
                NamespaceSummary(
                    namespace="team-prod",
                    requested_gpu_hours=24.0,
                    over_requested_gpu_hours=12.0,
                    estimated_request_cost=60.0,
                    estimated_over_request_cost=30.0,
                    avg_utilization=3.0,
                )
            ],
            action_items=[
                ActionItem(
                    priority="High",
                    category="Right-sizing",
                    target="team-prod/jupyter-alice",
                    action="Review team-prod/jupyter-alice on gpu-node-a.",
                    estimated_window_savings=12.5,
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "public"
            archive_path = Path(tmp) / "public.zip"

            manifest = write_public_bundle(
                "public",
                output_dir,
                archive_path,
                report,
                title="Public Case Study",
                cluster_name="demo-cluster",
                no_archive=False,
            )

            self.assertTrue(manifest["redacted"])
            self.assertIn("case-study.md", manifest["files"])
            combined = "\n".join(
                (output_dir / name).read_text(encoding="utf-8")
                for name in ("README.md", "audit.json", "audit.md", "case-study.md")
            )
            self.assertNotIn("team-prod", combined)
            self.assertNotIn("jupyter-alice", combined)
            self.assertNotIn("gpu-node-a", combined)
            self.assertNotIn("GPU-1234abcd", combined)
            self.assertIn("namespace-001", combined)
            self.assertIn("workload-001", combined)
            self.assertIn("node-001", combined)
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(
                    sorted(archive.namelist()),
                    [
                        "README.md",
                        "audit.html",
                        "audit.json",
                        "audit.md",
                        "case-study.md",
                        "manifest.json",
                    ],
                )


if __name__ == "__main__":
    unittest.main()
