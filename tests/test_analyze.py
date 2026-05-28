from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_gpu_lens.analyze import analyze_bundle, gpu_key, price_for_model
from ai_gpu_lens.model import MetricBundle, Series


class AnalyzeBundleTest(unittest.TestCase):
    def test_idle_hours_and_namespace_attribution(self) -> None:
        bundle = MetricBundle(
            gpu_utilization=(
                Series(
                    metric={
                        "Hostname": "gpu-node-1",
                        "UUID": "GPU-a",
                        "gpu": "0",
                        "namespace": "llm-prod",
                        "pod": "vllm-0",
                        "modelName": "NVIDIA H100 80GB HBM3",
                    },
                    values=((0, 0), (1800, 10), (3600, 80)),
                ),
                Series(
                    metric={
                        "Hostname": "gpu-node-1",
                        "UUID": "GPU-b",
                        "gpu": "1",
                        "namespace": "notebooks",
                        "pod": "jupyter-0",
                    },
                    values=((0, 0), (1800, 0), (3600, 0)),
                ),
            ),
            memory_used=(
                Series(
                    metric={"Hostname": "gpu-node-1", "UUID": "GPU-a", "gpu": "0"},
                    values=((0, 20000), (3600, 40000)),
                ),
            ),
            memory_total=(
                Series(
                    metric={"Hostname": "gpu-node-1", "UUID": "GPU-a", "gpu": "0"},
                    values=((0, 80000), (3600, 80000)),
                ),
            ),
            gpu_requests=(
                Series(
                    metric={"namespace": "llm-prod", "pod": "vllm-0"},
                    values=((0, 1), (1800, 1), (3600, 1)),
                ),
                Series(
                    metric={"namespace": "notebooks", "pod": "jupyter-0"},
                    values=((0, 1), (1800, 1), (3600, 1)),
                ),
            ),
        )

        report = analyze_bundle(
            bundle,
            window_hours=1.0,
            step="30m",
            price_per_gpu_hour=2.0,
        )

        self.assertEqual(report.total_gpus, 2)
        self.assertEqual(report.language, "en")
        self.assertAlmostEqual(report.total_idle_gpu_hours, 1.3333333333)
        self.assertAlmostEqual(report.estimated_idle_cost, 2.6666666666)
        self.assertAlmostEqual(report.total_requested_gpu_hours, 2.0)
        self.assertAlmostEqual(report.estimated_request_cost, 4.0)
        self.assertEqual(report.namespaces[0].namespace, "llm-prod")
        self.assertAlmostEqual(
            report.namespaces[0].utilized_gpu_hour_equivalent,
            0.3,
        )
        self.assertIn(
            "Memory used metric is missing for one or more GPUs.",
            report.telemetry_gaps,
        )

    def test_dedupes_duplicate_dcgm_series_by_physical_gpu(self) -> None:
        bundle = MetricBundle(
            gpu_utilization=(
                Series(
                    metric={
                        "Hostname": "gpu-node-1",
                        "UUID": "GPU-a",
                        "gpu": "0",
                        "namespace": "llm-prod",
                        "pod": "vllm-0",
                    },
                    values=((0, 10), (3600, 20)),
                ),
                Series(
                    metric={
                        "Hostname": "gpu-node-1",
                        "UUID": "GPU-a",
                        "gpu": "0",
                        "namespace": "llm-prod",
                        "pod": "sidecar-0",
                    },
                    values=((0, 10), (3600, 20)),
                ),
            )
        )

        report = analyze_bundle(bundle, window_hours=1.0, step="1h")

        self.assertEqual(report.total_gpus, 1)
        self.assertEqual(report.gpus[0].source_series_count, 2)
        self.assertEqual(report.gpus[0].pod, "mixed")
        self.assertIn(
            "One or more physical GPUs had duplicate DCGM series and were deduplicated by GPU UUID/index.",
            report.telemetry_gaps,
        )

    def test_prices_can_match_gpu_model_substrings(self) -> None:
        self.assertEqual(
            price_for_model(
                "NVIDIA H100 80GB HBM3",
                {"H100": 4.25, "default": 2.0},
                1.0,
            ),
            4.25,
        )
        self.assertEqual(price_for_model("unknown", {"default": 2.0}, 1.0), 2.0)

    def test_dcgm_exporter_self_namespace_is_not_workload_namespace(self) -> None:
        bundle = MetricBundle(
            gpu_utilization=(
                Series(
                    metric={
                        "Hostname": "gpu-node-1",
                        "UUID": "GPU-a",
                        "gpu": "0",
                        "job": "nvidia-dcgm-exporter",
                        "namespace": "gpu-operator",
                        "pod": "nvidia-dcgm-exporter-abcde",
                        "exported_namespace": "slurm",
                        "exported_pod": "gpu-l40s-0",
                    },
                    values=((0, 10), (3600, 20)),
                ),
                Series(
                    metric={
                        "Hostname": "gpu-node-1",
                        "UUID": "GPU-b",
                        "gpu": "1",
                        "job": "nvidia-dcgm-exporter",
                        "namespace": "gpu-operator",
                        "pod": "nvidia-dcgm-exporter-abcde",
                    },
                    values=((0, 0), (3600, 0)),
                ),
            )
        )

        report = analyze_bundle(bundle, window_hours=1.0, step="1h")

        self.assertEqual(report.gpus[0].namespace, "slurm")
        self.assertEqual(report.gpus[0].pod, "gpu-l40s-0")
        self.assertEqual(report.gpus[1].namespace, "unknown")

    def test_chinese_recommendations_and_gaps(self) -> None:
        bundle = MetricBundle(
            gpu_utilization=(
                Series(
                    metric={"Hostname": "gpu-node-1", "UUID": "GPU-a", "gpu": "0"},
                    values=((0, 0), (3600, 0)),
                ),
            )
        )

        report = analyze_bundle(
            bundle,
            window_hours=1.0,
            step="1h",
            price_per_gpu_hour=2.0,
            language="zh",
        )

        self.assertEqual(report.language, "zh")
        self.assertIn("排查 1 条平均利用率低于 5% 的 GPU 序列。", report.recommendations)
        self.assertIn(
            "GPU 利用率序列缺少 Kubernetes namespace 标签。",
            report.telemetry_gaps,
        )

    def test_gpu_key_prefers_uuid(self) -> None:
        key = gpu_key({"node": "node-a", "UUID": "GPU-123", "gpu": "0"})
        self.assertEqual(key, "node-a/GPU-123")

    def test_gpu_key_falls_back_to_index(self) -> None:
        key = gpu_key({"Hostname": "node-a", "gpu": "3"})
        self.assertEqual(key, "node-a/gpu-3")


if __name__ == "__main__":
    unittest.main()
