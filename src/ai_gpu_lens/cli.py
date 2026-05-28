from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from . import __version__
from .analyze import analyze_bundle
from .i18n import SUPPORTED_LANGUAGES, normalize_language, t
from .prometheus import (
    DEFAULT_GPU_UTIL_QUERY,
    DEFAULT_MEMORY_TOTAL_QUERY,
    DEFAULT_MEMORY_USED_QUERY,
    PrometheusError,
    collect_bundle,
    load_bundle,
)
from .report import write_html_report, write_json_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-gpu-lens",
        description="Generate GPU fleet audit reports from Prometheus/DCGM metrics.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser(
        "audit",
        help="Generate an HTML/JSON audit report.",
    )
    source = audit.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--prometheus-url",
        help="Prometheus base URL, for example http://localhost:9090.",
    )
    source.add_argument(
        "--from-file",
        type=Path,
        help="Read a saved metric bundle JSON file.",
    )
    audit.add_argument(
        "--hours",
        type=float,
        default=24.0,
        help="Query window in hours. Default: 24.",
    )
    audit.add_argument(
        "--step",
        default="5m",
        help="Prometheus query_range step. Default: 5m.",
    )
    audit.add_argument(
        "--output",
        type=Path,
        default=Path("reports/gpu-audit.html"),
        help="HTML report path. Default: reports/gpu-audit.html.",
    )
    audit.add_argument(
        "--json-output",
        type=Path,
        help="Optional JSON report path.",
    )
    audit.add_argument(
        "--price-per-gpu-hour",
        type=float,
        default=0.0,
        help="Cost used to estimate idle spend.",
    )
    audit.add_argument(
        "--idle-threshold",
        type=float,
        default=5.0,
        help="Utilization percent below which a sample is idle. Default: 5.",
    )
    audit.add_argument(
        "--active-threshold",
        type=float,
        default=10.0,
        help="Utilization percent at or above which a sample is active. Default: 10.",
    )
    audit.add_argument(
        "--gpu-util-query",
        default=DEFAULT_GPU_UTIL_QUERY,
        help="PromQL for GPU utilization. Default: DCGM_FI_DEV_GPU_UTIL.",
    )
    audit.add_argument(
        "--memory-used-query",
        default=DEFAULT_MEMORY_USED_QUERY,
        help="PromQL for framebuffer memory used. Default: DCGM_FI_DEV_FB_USED.",
    )
    audit.add_argument(
        "--memory-total-query",
        default=DEFAULT_MEMORY_TOTAL_QUERY,
        help="PromQL for framebuffer memory total. Default: DCGM_FI_DEV_FB_TOTAL.",
    )
    audit.add_argument(
        "--language",
        choices=SUPPORTED_LANGUAGES,
        default="en",
        help="Report language: en or zh. Default: en.",
    )
    audit.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Prometheus HTTP timeout in seconds. Default: 20.",
    )
    audit.set_defaults(func=run_audit)
    return parser


def run_audit(args: argparse.Namespace) -> int:
    language = normalize_language(args.language)
    if args.from_file:
        bundle = load_bundle(args.from_file)
    else:
        try:
            bundle = collect_bundle(
                args.prometheus_url,
                hours=args.hours,
                step=args.step,
                gpu_util_query=args.gpu_util_query,
                memory_used_query=args.memory_used_query,
                memory_total_query=args.memory_total_query,
                timeout=args.timeout,
            )
        except PrometheusError as exc:
            print(f"error: {exc}")
            return 2

    report = analyze_bundle(
        bundle,
        window_hours=args.hours,
        step=args.step,
        price_per_gpu_hour=args.price_per_gpu_hour,
        idle_threshold=args.idle_threshold,
        active_threshold=args.active_threshold,
        language=language,
    )
    write_html_report(report, args.output)
    if args.json_output:
        write_json_report(report, args.json_output)

    print(t(language, "wrote_html", path=args.output))
    if args.json_output:
        print(t(language, "json_written", path=args.json_output))
    print(
        t(
            language,
            "summary",
            gpus=report.total_gpus,
            util=report.fleet_avg_utilization,
            idle_hours=report.total_idle_gpu_hours,
        )
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
