from __future__ import annotations

import argparse
import getpass
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from . import __version__
from .analyze import analyze_bundle
from .config import (
    ConfigError,
    config_path,
    get_config_value,
    load_config,
    normalize_gpu_prices,
    parse_gpu_prices,
)
from .compare import (
    build_comparison,
    load_audit_report,
    write_comparison_html,
    write_comparison_json,
    write_comparison_markdown,
)
from .dashboard import (
    DEFAULT_DASHBOARD_TITLE,
    DEFAULT_DASHBOARD_UID,
    DEFAULT_DATASOURCE_UID,
    DEFAULT_MEMORY_TOTAL_OR_FALLBACK_QUERY,
    build_grafana_dashboard,
    write_dashboard_json,
)
from .i18n import SUPPORTED_LANGUAGES, normalize_language, t
from .doctor import render_doctor_text, run_doctor
from .model import AuditReport
from .prometheus import (
    DEFAULT_GPU_UTIL_QUERY,
    DEFAULT_KUBE_GPU_REQUEST_QUERY,
    DEFAULT_MEMORY_TOTAL_FALLBACK_QUERY,
    DEFAULT_MEMORY_TOTAL_QUERY,
    DEFAULT_MEMORY_USED_QUERY,
    PrometheusError,
    collect_bundle,
    load_bundle,
)
from .redact import (
    audit_report_from_mapping,
    is_audit_report,
    load_json_report,
    redact_report,
    render_case_study,
    write_json,
)
from .report import write_html_report, write_json_report, write_markdown_report


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
    audit.add_argument(
        "--config",
        type=Path,
        help="Optional ai-gpu-lens YAML/JSON config file.",
    )
    source = audit.add_mutually_exclusive_group()
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
        default=None,
        help="Query window in hours. Default: 24.",
    )
    audit.add_argument(
        "--step",
        default=None,
        help="Prometheus query_range step. Default: 5m.",
    )
    audit.add_argument(
        "--output",
        type=Path,
        default=None,
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
        default=None,
        help="Cost used to estimate idle spend.",
    )
    audit.add_argument(
        "--gpu-price",
        action="append",
        help="Override price for a GPU model, MODEL=PRICE. Can be repeated.",
    )
    audit.add_argument(
        "--idle-threshold",
        type=float,
        default=None,
        help="Utilization percent below which a sample is idle. Default: 5.",
    )
    audit.add_argument(
        "--active-threshold",
        type=float,
        default=None,
        help="Utilization percent at or above which a sample is active. Default: 10.",
    )
    audit.add_argument(
        "--gpu-util-query",
        default=None,
        help="PromQL for GPU utilization. Default: DCGM_FI_DEV_GPU_UTIL.",
    )
    audit.add_argument(
        "--memory-used-query",
        default=None,
        help="PromQL for framebuffer memory used. Default: DCGM_FI_DEV_FB_USED.",
    )
    audit.add_argument(
        "--memory-total-query",
        default=None,
        help="PromQL for framebuffer memory total. Default: DCGM_FI_DEV_FB_TOTAL.",
    )
    audit.add_argument(
        "--memory-total-fallback-query",
        default=None,
        help="Fallback PromQL for framebuffer memory total.",
    )
    audit.add_argument(
        "--skip-memory-total-fallback",
        action="store_true",
        help="Do not try the framebuffer memory total fallback query.",
    )
    audit.add_argument(
        "--kube-gpu-request-query",
        default=None,
        help="PromQL for kube-state-metrics GPU requests.",
    )
    audit.add_argument(
        "--skip-kube-gpu-requests",
        action="store_true",
        help="Do not query kube-state-metrics GPU request data.",
    )
    audit.add_argument(
        "--language",
        choices=SUPPORTED_LANGUAGES,
        default=None,
        help="Report language: en or zh. Default: en.",
    )
    audit.add_argument(
        "--markdown-output",
        type=Path,
        help="Optional Markdown report path.",
    )
    audit.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Prometheus HTTP timeout in seconds. Default: 20.",
    )
    audit.add_argument(
        "--basic-auth-user",
        help="HTTP Basic Auth username for Prometheus or a Grafana datasource proxy.",
    )
    audit.add_argument(
        "--basic-auth-password-env",
        help="Environment variable containing the HTTP Basic Auth password.",
    )
    audit.add_argument(
        "--prompt-basic-auth-password",
        action="store_true",
        help="Prompt for the HTTP Basic Auth password without storing it.",
    )
    audit.add_argument(
        "--bearer-token-env",
        help="Environment variable containing a Bearer token.",
    )
    audit.set_defaults(func=run_audit)

    bundle = subparsers.add_parser(
        "bundle",
        help="Generate a complete audit delivery bundle.",
    )
    bundle.add_argument(
        "--config",
        type=Path,
        help="Optional ai-gpu-lens YAML/JSON config file.",
    )
    bundle_source = bundle.add_mutually_exclusive_group()
    bundle_source.add_argument(
        "--prometheus-url",
        help="Prometheus base URL, for example http://localhost:9090.",
    )
    bundle_source.add_argument(
        "--from-file",
        type=Path,
        help="Read a saved metric bundle JSON file.",
    )
    bundle.add_argument(
        "--name",
        default=None,
        help="Bundle name. Default: gpu-audit.",
    )
    bundle.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for bundle files. Default: reports/<name>.",
    )
    bundle.add_argument(
        "--archive",
        type=Path,
        default=None,
        help="Zip archive path. Default: <output-dir>.zip.",
    )
    bundle.add_argument(
        "--no-archive",
        action="store_true",
        help="Write bundle files without creating a zip archive.",
    )
    bundle.add_argument(
        "--skip-doctor",
        action="store_true",
        help="Skip doctor output even when using a live Prometheus/Grafana endpoint.",
    )
    bundle.add_argument(
        "--hours",
        type=float,
        default=None,
        help="Query window in hours. Default: 24.",
    )
    bundle.add_argument(
        "--step",
        default=None,
        help="Prometheus query_range step. Default: 5m.",
    )
    bundle.add_argument(
        "--price-per-gpu-hour",
        type=float,
        default=None,
        help="Cost used to estimate idle spend.",
    )
    bundle.add_argument(
        "--gpu-price",
        action="append",
        help="Override price for a GPU model, MODEL=PRICE. Can be repeated.",
    )
    bundle.add_argument(
        "--idle-threshold",
        type=float,
        default=None,
        help="Utilization percent below which a sample is idle. Default: 5.",
    )
    bundle.add_argument(
        "--active-threshold",
        type=float,
        default=None,
        help="Utilization percent at or above which a sample is active. Default: 10.",
    )
    bundle.add_argument(
        "--gpu-util-query",
        default=None,
        help="PromQL for GPU utilization. Default: DCGM_FI_DEV_GPU_UTIL.",
    )
    bundle.add_argument(
        "--memory-used-query",
        default=None,
        help="PromQL for framebuffer memory used. Default: DCGM_FI_DEV_FB_USED.",
    )
    bundle.add_argument(
        "--memory-total-query",
        default=None,
        help="PromQL for framebuffer memory total. Default: DCGM_FI_DEV_FB_TOTAL.",
    )
    bundle.add_argument(
        "--memory-total-fallback-query",
        default=None,
        help="Fallback PromQL for framebuffer memory total.",
    )
    bundle.add_argument(
        "--skip-memory-total-fallback",
        action="store_true",
        help="Do not try the framebuffer memory total fallback query.",
    )
    bundle.add_argument(
        "--kube-gpu-request-query",
        default=None,
        help="PromQL for kube-state-metrics GPU requests.",
    )
    bundle.add_argument(
        "--skip-kube-gpu-requests",
        action="store_true",
        help="Do not query kube-state-metrics GPU request data.",
    )
    bundle.add_argument(
        "--language",
        choices=SUPPORTED_LANGUAGES,
        default=None,
        help="Report language: en or zh. Default: en.",
    )
    bundle.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Prometheus HTTP timeout in seconds. Default: 20.",
    )
    bundle.add_argument(
        "--basic-auth-user",
        help="HTTP Basic Auth username for Prometheus or a Grafana datasource proxy.",
    )
    bundle.add_argument(
        "--basic-auth-password-env",
        help="Environment variable containing the HTTP Basic Auth password.",
    )
    bundle.add_argument(
        "--prompt-basic-auth-password",
        action="store_true",
        help="Prompt for the HTTP Basic Auth password without storing it.",
    )
    bundle.add_argument(
        "--bearer-token-env",
        help="Environment variable containing a Bearer token.",
    )
    bundle.set_defaults(func=run_bundle)

    compare = subparsers.add_parser(
        "compare",
        help="Compare two audit JSON reports.",
    )
    compare.add_argument(
        "--before",
        type=Path,
        required=True,
        help="Baseline audit JSON report.",
    )
    compare.add_argument(
        "--after",
        type=Path,
        required=True,
        help="Follow-up audit JSON report.",
    )
    compare.add_argument(
        "--output",
        type=Path,
        default=Path("reports/gpu-comparison.html"),
        help="HTML comparison report path.",
    )
    compare.add_argument(
        "--json-output",
        type=Path,
        help="Optional JSON comparison report path.",
    )
    compare.add_argument(
        "--markdown-output",
        type=Path,
        help="Optional Markdown comparison report path.",
    )
    compare.add_argument(
        "--language",
        choices=SUPPORTED_LANGUAGES,
        default=None,
        help="Report language: en or zh. Default: after report language or en.",
    )
    compare.set_defaults(func=run_compare)

    dashboard = subparsers.add_parser(
        "dashboard",
        help="Generate an importable Grafana dashboard JSON file.",
    )
    dashboard.add_argument(
        "--config",
        type=Path,
        help="Optional ai-gpu-lens YAML/JSON config file.",
    )
    dashboard.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Dashboard JSON path. Default: reports/ai-gpu-lens-dashboard.json.",
    )
    dashboard.add_argument(
        "--title",
        default=None,
        help=f"Grafana dashboard title. Default: {DEFAULT_DASHBOARD_TITLE}.",
    )
    dashboard.add_argument(
        "--uid",
        default=None,
        help=f"Grafana dashboard UID. Default: {DEFAULT_DASHBOARD_UID}.",
    )
    dashboard.add_argument(
        "--datasource-uid",
        default=None,
        help=(
            "Prometheus datasource UID. Default prompts for a datasource on "
            "Grafana import."
        ),
    )
    dashboard.add_argument(
        "--time-from",
        default=None,
        help="Default dashboard time range start. Default: now-24h.",
    )
    dashboard.add_argument(
        "--refresh",
        default=None,
        help="Default dashboard refresh interval. Default: 1m.",
    )
    dashboard.add_argument(
        "--gpu-util-query",
        default=None,
        help="PromQL metric/expression for GPU utilization.",
    )
    dashboard.add_argument(
        "--memory-used-query",
        default=None,
        help="PromQL metric/expression for framebuffer memory used.",
    )
    dashboard.add_argument(
        "--memory-total-query",
        default=None,
        help=(
            "PromQL metric/expression for framebuffer memory total. Default "
            "uses DCGM_FI_DEV_FB_TOTAL with a used+free fallback."
        ),
    )
    dashboard.add_argument(
        "--kube-gpu-request-query",
        default=None,
        help="PromQL metric/expression for kube-state-metrics GPU requests.",
    )
    dashboard.add_argument(
        "--skip-kube-gpu-requests",
        action="store_true",
        help="Do not include requested-GPU panels.",
    )
    dashboard.set_defaults(func=run_dashboard)

    redact = subparsers.add_parser(
        "redact",
        help="Redact sensitive identifiers from report JSON.",
    )
    redact.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input JSON report path.",
    )
    redact.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Redacted JSON report path.",
    )
    redact.add_argument(
        "--html-output",
        type=Path,
        help="Optional redacted HTML audit report path.",
    )
    redact.add_argument(
        "--markdown-output",
        type=Path,
        help="Optional redacted Markdown audit report path.",
    )
    redact.add_argument(
        "--case-study-output",
        type=Path,
        help="Optional public case study Markdown path for audit reports.",
    )
    redact.add_argument(
        "--title",
        default="Anonymized GPU Audit Case Study",
        help="Case study title.",
    )
    redact.add_argument(
        "--cluster-name",
        default="anonymized-cluster",
        help="Public cluster name used in the case study.",
    )
    redact.add_argument(
        "--language",
        choices=SUPPORTED_LANGUAGES,
        default=None,
        help="Output language for rendered audit/case-study artifacts.",
    )
    redact.set_defaults(func=run_redact)

    doctor = subparsers.add_parser(
        "doctor",
        help="Check whether a Prometheus or Grafana datasource proxy is audit-ready.",
    )
    doctor.add_argument(
        "--config",
        type=Path,
        help="Optional ai-gpu-lens YAML/JSON config file.",
    )
    doctor.add_argument(
        "--prometheus-url",
        help="Prometheus base URL or Grafana datasource proxy URL.",
    )
    doctor.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Prometheus HTTP timeout in seconds. Default: 20.",
    )
    doctor.add_argument(
        "--json-output",
        type=Path,
        help="Optional JSON doctor report path.",
    )
    doctor.add_argument(
        "--basic-auth-user",
        help="HTTP Basic Auth username for Prometheus or a Grafana datasource proxy.",
    )
    doctor.add_argument(
        "--basic-auth-password-env",
        help="Environment variable containing the HTTP Basic Auth password.",
    )
    doctor.add_argument(
        "--prompt-basic-auth-password",
        action="store_true",
        help="Prompt for the HTTP Basic Auth password without storing it.",
    )
    doctor.add_argument(
        "--bearer-token-env",
        help="Environment variable containing a Bearer token.",
    )
    doctor.set_defaults(func=run_doctor_command)
    return parser


def run_audit(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        options = resolve_options(args, config)
    except ConfigError as exc:
        print(f"error: {exc}")
        return 2

    language = normalize_language(options["language"])
    try:
        report = build_audit_report(options)
    except PrometheusError as exc:
        print(f"error: {exc}")
        return 2
    write_html_report(report, options["output"])
    if options["json_output"]:
        write_json_report(report, options["json_output"])
    if options["markdown_output"]:
        write_markdown_report(report, options["markdown_output"])

    print(t(language, "wrote_html", path=options["output"]))
    if options["json_output"]:
        print(t(language, "json_written", path=options["json_output"]))
    if options["markdown_output"]:
        print(t(language, "wrote_markdown", path=options["markdown_output"]))
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


def build_audit_report(options: dict[str, object]) -> AuditReport:
    language = normalize_language(str(options["language"]))
    if options["from_file"]:
        bundle = load_bundle(options["from_file"])
    else:
        bundle = collect_bundle(
            str(options["prometheus_url"]),
            hours=float(options["hours"]),
            step=str(options["step"]),
            gpu_util_query=str(options["gpu_util_query"]),
            memory_used_query=str(options["memory_used_query"]),
            memory_total_query=str(options["memory_total_query"]),
            memory_total_fallback_query=options["memory_total_fallback_query"],
            kube_gpu_request_query=options["kube_gpu_request_query"],
            timeout=float(options["timeout"]),
            basic_auth=options["basic_auth"],
            bearer_token=options["bearer_token"],
        )

    return analyze_bundle(
        bundle,
        window_hours=float(options["hours"]),
        step=str(options["step"]),
        price_per_gpu_hour=float(options["price_per_gpu_hour"]),
        gpu_prices=options["gpu_prices"],
        idle_threshold=float(options["idle_threshold"]),
        active_threshold=float(options["active_threshold"]),
        language=language,
    )


def run_bundle(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        bundle_name = str(
            args.name or get_config_value(config, "bundle_name", "gpu-audit")
        )
        output_dir = (
            args.output_dir
            or config_path(get_config_value(config, "bundle_output_dir"))
            or Path("reports") / bundle_name
        )
        archive_path = (
            args.archive
            or config_path(get_config_value(config, "bundle_archive"))
            or output_dir.parent / f"{output_dir.name}.zip"
        )
        args.output = output_dir / "audit.html"
        args.json_output = output_dir / "audit.json"
        args.markdown_output = output_dir / "audit.md"
        options = resolve_options(args, config)
    except ConfigError as exc:
        print(f"error: {exc}")
        return 2

    try:
        report = build_audit_report(options)
    except PrometheusError as exc:
        print(f"error: {exc}")
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)
    clear_bundle_outputs(output_dir)
    write_html_report(report, options["output"])
    write_json_report(report, options["json_output"])
    write_markdown_report(report, options["markdown_output"])

    doctor_report = None
    skip_doctor = bool(
        args.skip_doctor or get_config_value(config, "bundle_skip_doctor", False)
    )
    if options["prometheus_url"] and not skip_doctor:
        try:
            doctor_report = run_doctor(
                str(options["prometheus_url"]),
                timeout=float(options["timeout"]),
                basic_auth=options["basic_auth"],
                bearer_token=options["bearer_token"],
            )
        except PrometheusError as exc:
            print(f"warning: doctor failed: {exc}")
        else:
            (output_dir / "doctor.json").write_text(
                json.dumps(doctor_report.to_dict(), indent=2) + "\n",
                encoding="utf-8",
            )
            (output_dir / "doctor.txt").write_text(
                render_doctor_text(doctor_report) + "\n",
                encoding="utf-8",
            )

    manifest = build_bundle_manifest(
        bundle_name,
        output_dir,
        report,
        source="file" if options["from_file"] else "prometheus",
        doctor_included=doctor_report is not None,
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "README.md").write_text(
        render_bundle_readme(bundle_name, report, manifest),
        encoding="utf-8",
    )

    print(f"wrote bundle directory: {output_dir}")
    no_archive = bool(
        args.no_archive or get_config_value(config, "bundle_no_archive", False)
    )
    if not no_archive:
        archive_bundle(output_dir, archive_path)
        print(f"wrote bundle archive: {archive_path}")
    print(
        t(
            report.language,
            "summary",
            gpus=report.total_gpus,
            util=report.fleet_avg_utilization,
            idle_hours=report.total_idle_gpu_hours,
        )
    )
    return 0


def build_bundle_manifest(
    bundle_name: str,
    output_dir: Path,
    report: AuditReport,
    *,
    source: str,
    doctor_included: bool,
) -> dict[str, object]:
    files = [
        str(path.relative_to(output_dir))
        for path in sorted(output_dir.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    ]
    files.extend(["manifest.json", "README.md"])
    return {
        "name": bundle_name,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ai_gpu_lens_version": __version__,
        "source": source,
        "doctor_included": doctor_included,
        "window_hours": report.window_hours,
        "step": report.step,
        "language": report.language,
        "total_gpus": report.total_gpus,
        "fleet_avg_utilization": report.fleet_avg_utilization,
        "total_idle_gpu_hours": report.total_idle_gpu_hours,
        "estimated_idle_cost": report.estimated_idle_cost,
        "total_requested_gpu_hours": report.total_requested_gpu_hours,
        "estimated_request_cost": report.estimated_request_cost,
        "files": sorted(set(files)),
    }


def clear_bundle_outputs(output_dir: Path) -> None:
    for name in (
        "README.md",
        "audit.html",
        "audit.json",
        "audit.md",
        "doctor.json",
        "doctor.txt",
        "manifest.json",
    ):
        path = output_dir / name
        if path.exists():
            path.unlink()


def render_bundle_readme(
    bundle_name: str,
    report: AuditReport,
    manifest: dict[str, object],
) -> str:
    action_items = "\n".join(
        "- [{priority}] {target}: {action} (${savings:,.2f})".format(
            priority=item.priority,
            target=item.target,
            action=item.action,
            savings=item.estimated_window_savings,
        )
        for item in report.action_items
    )
    if not action_items:
        action_items = "- n/a"
    telemetry_gaps = "\n".join(f"- {item}" for item in report.telemetry_gaps)
    if not telemetry_gaps:
        telemetry_gaps = "- n/a"
    files = "\n".join(f"- `{item}`" for item in manifest["files"])
    return f"""# {bundle_name}

Generated by ai-gpu-lens {__version__}.

## Summary

- GPUs: {report.total_gpus}
- Window: {report.window_hours:.2f}h, step {report.step}
- Fleet average utilization: {report.fleet_avg_utilization:.1f}%
- Idle GPU hours: {report.total_idle_gpu_hours:,.2f}
- Estimated idle cost: ${report.estimated_idle_cost:,.2f}
- Requested GPU hours: {report.total_requested_gpu_hours:,.2f}
- Estimated requested cost: ${report.estimated_request_cost:,.2f}

## Files

{files}

## Action Items

{action_items}

## Telemetry Gaps

{telemetry_gaps}
"""


def archive_bundle(output_dir: Path, archive_path: Path) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_resolved = archive_path.resolve()
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.resolve() == archive_resolved:
                continue
            archive.write(path, path.relative_to(output_dir))


def run_compare(args: argparse.Namespace) -> int:
    try:
        before = load_audit_report(args.before)
        after = load_audit_report(args.after)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 2
    try:
        language = normalize_language(args.language or str(after.get("language", "en")))
    except ValueError as exc:
        print(f"error: {exc}")
        return 2
    report = build_comparison(before, after, language=language)
    write_comparison_html(report, args.output)
    if args.json_output:
        write_comparison_json(report, args.json_output)
    if args.markdown_output:
        write_comparison_markdown(report, args.markdown_output)
    print(f"wrote HTML comparison report: {args.output}")
    if args.json_output:
        print(f"wrote JSON comparison report: {args.json_output}")
    if args.markdown_output:
        print(f"wrote Markdown comparison report: {args.markdown_output}")
    for item in report.summary:
        print(f"- {item}")
    return 0


def run_dashboard(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"error: {exc}")
        return 2

    kube_gpu_request_query = (
        args.kube_gpu_request_query
        if args.kube_gpu_request_query is not None
        else get_config_value(
            config,
            "kube_gpu_request_query",
            DEFAULT_KUBE_GPU_REQUEST_QUERY,
        )
    )
    if bool(
        args.skip_kube_gpu_requests
        or get_config_value(config, "skip_kube_gpu_requests", False)
    ):
        kube_gpu_request_query = None

    dashboard = build_grafana_dashboard(
        title=str(
            args.title
            or get_config_value(config, "dashboard_title", DEFAULT_DASHBOARD_TITLE)
        ),
        uid=str(args.uid or get_config_value(config, "dashboard_uid", DEFAULT_DASHBOARD_UID)),
        datasource_uid=str(
            args.datasource_uid
            or get_config_value(config, "dashboard_datasource_uid", DEFAULT_DATASOURCE_UID)
        ),
        gpu_util_query=str(
            args.gpu_util_query
            or get_config_value(config, "gpu_util_query", DEFAULT_GPU_UTIL_QUERY)
        ),
        memory_used_query=str(
            args.memory_used_query
            or get_config_value(config, "memory_used_query", DEFAULT_MEMORY_USED_QUERY)
        ),
        memory_total_query=str(
            args.memory_total_query
            or get_config_value(
                config,
                "dashboard_memory_total_query",
                get_config_value(
                    config,
                    "memory_total_query",
                    DEFAULT_MEMORY_TOTAL_OR_FALLBACK_QUERY,
                ),
            )
        ),
        kube_gpu_request_query=kube_gpu_request_query,
        time_from=str(args.time_from or get_config_value(config, "dashboard_time_from", "now-24h")),
        refresh=str(args.refresh or get_config_value(config, "dashboard_refresh", "1m")),
    )
    output = (
        args.output
        or config_path(get_config_value(config, "dashboard_output"))
        or Path("reports/ai-gpu-lens-dashboard.json")
    )
    write_dashboard_json(dashboard, output)
    print(f"wrote Grafana dashboard JSON: {output}")
    return 0


def run_redact(args: argparse.Namespace) -> int:
    try:
        payload = load_json_report(args.input)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 2

    redacted, _redactions = redact_report(payload)
    try:
        language = normalize_language(args.language or str(redacted.get("language", "en")))
    except ValueError as exc:
        print(f"error: {exc}")
        return 2
    redacted["language"] = language
    write_json(redacted, args.output)
    print(f"wrote redacted JSON report: {args.output}")

    if args.html_output or args.markdown_output or args.case_study_output:
        if not is_audit_report(redacted):
            print("error: HTML, Markdown, and case-study outputs require an audit JSON report")
            return 2
        audit_report = audit_report_from_mapping(redacted)
        if args.html_output:
            write_html_report(audit_report, args.html_output)
            print(f"wrote redacted HTML report: {args.html_output}")
        if args.markdown_output:
            write_markdown_report(audit_report, args.markdown_output)
            print(f"wrote redacted Markdown report: {args.markdown_output}")
        if args.case_study_output:
            args.case_study_output.parent.mkdir(parents=True, exist_ok=True)
            args.case_study_output.write_text(
                render_case_study(
                    redacted,
                    title=args.title,
                    cluster_name=args.cluster_name,
                    language=language,
                ),
                encoding="utf-8",
            )
            print(f"wrote public case study: {args.case_study_output}")
    return 0


def resolve_options(args: argparse.Namespace, config: dict[str, object]) -> dict[str, object]:
    from_file = args.from_file or config_path(get_config_value(config, "from_file"))
    prometheus_url = args.prometheus_url or get_config_value(config, "prometheus_url")
    if from_file and prometheus_url:
        raise ConfigError("choose only one source: from_file or prometheus_url")
    if not from_file and not prometheus_url:
        raise ConfigError("provide --from-file, --prometheus-url, or set one in config")

    gpu_prices = normalize_gpu_prices(get_config_value(config, "gpu_prices", {}))
    gpu_prices.update(parse_gpu_prices(args.gpu_price))

    kube_gpu_request_query = (
        args.kube_gpu_request_query
        if args.kube_gpu_request_query is not None
        else get_config_value(
            config,
            "kube_gpu_request_query",
            DEFAULT_KUBE_GPU_REQUEST_QUERY,
        )
    )
    skip_requests = bool(
        args.skip_kube_gpu_requests
        or get_config_value(config, "skip_kube_gpu_requests", False)
    )
    if skip_requests:
        kube_gpu_request_query = None
    memory_total_fallback_query = (
        args.memory_total_fallback_query
        if args.memory_total_fallback_query is not None
        else get_config_value(
            config,
            "memory_total_fallback_query",
            DEFAULT_MEMORY_TOTAL_FALLBACK_QUERY,
        )
    )
    if bool(
        args.skip_memory_total_fallback
        or get_config_value(config, "skip_memory_total_fallback", False)
    ):
        memory_total_fallback_query = None

    return {
        "from_file": from_file,
        "prometheus_url": prometheus_url,
        "hours": float(args.hours or get_config_value(config, "hours", 24.0)),
        "step": str(args.step or get_config_value(config, "step", "5m")),
        "output": args.output
        or config_path(get_config_value(config, "output"))
        or Path("reports/gpu-audit.html"),
        "json_output": args.json_output
        or config_path(get_config_value(config, "json_output")),
        "markdown_output": args.markdown_output
        or config_path(get_config_value(config, "markdown_output")),
        "price_per_gpu_hour": float(
            args.price_per_gpu_hour
            if args.price_per_gpu_hour is not None
            else get_config_value(config, "price_per_gpu_hour", 0.0)
        ),
        "gpu_prices": gpu_prices,
        "idle_threshold": float(
            args.idle_threshold
            if args.idle_threshold is not None
            else get_config_value(config, "idle_threshold", 5.0)
        ),
        "active_threshold": float(
            args.active_threshold
            if args.active_threshold is not None
            else get_config_value(config, "active_threshold", 10.0)
        ),
        "gpu_util_query": str(
            args.gpu_util_query
            or get_config_value(config, "gpu_util_query", DEFAULT_GPU_UTIL_QUERY)
        ),
        "memory_used_query": str(
            args.memory_used_query
            or get_config_value(config, "memory_used_query", DEFAULT_MEMORY_USED_QUERY)
        ),
        "memory_total_query": str(
            args.memory_total_query
            or get_config_value(config, "memory_total_query", DEFAULT_MEMORY_TOTAL_QUERY)
        ),
        "memory_total_fallback_query": memory_total_fallback_query,
        "kube_gpu_request_query": kube_gpu_request_query,
        "language": str(args.language or get_config_value(config, "language", "en")),
        "timeout": float(args.timeout or get_config_value(config, "timeout", 20.0)),
        "basic_auth": resolve_basic_auth(args, config),
        "bearer_token": resolve_bearer_token(args, config),
    }


def run_doctor_command(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        prometheus_url = args.prometheus_url or get_config_value(
            config,
            "prometheus_url",
        )
        if not prometheus_url:
            raise ConfigError("provide --prometheus-url or set prometheus_url in config")
        report = run_doctor(
            str(prometheus_url),
            timeout=float(args.timeout or get_config_value(config, "timeout", 20.0)),
            basic_auth=resolve_basic_auth(args, config),
            bearer_token=resolve_bearer_token(args, config),
        )
    except ConfigError as exc:
        print(f"error: {exc}")
        return 2
    print(render_doctor_text(report))
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return 0


def resolve_basic_auth(
    args: argparse.Namespace,
    config: dict[str, object],
) -> tuple[str, str] | None:
    username = args.basic_auth_user or get_config_value(config, "basic_auth_user")
    password_env = args.basic_auth_password_env or get_config_value(
        config,
        "basic_auth_password_env",
    )
    prompt = bool(
        args.prompt_basic_auth_password
        or get_config_value(config, "prompt_basic_auth_password", False)
    )
    if not username:
        return None
    password = None
    if password_env:
        password = os.environ.get(str(password_env))
        if password is None:
            raise ConfigError(f"environment variable is not set: {password_env}")
    elif prompt:
        password = getpass.getpass("HTTP Basic Auth password: ")
    else:
        raise ConfigError(
            "basic auth user requires --prompt-basic-auth-password or "
            "--basic-auth-password-env"
        )
    return (str(username), password)


def resolve_bearer_token(
    args: argparse.Namespace,
    config: dict[str, object],
) -> str | None:
    token_env = args.bearer_token_env or get_config_value(config, "bearer_token_env")
    if not token_env:
        return None
    token = os.environ.get(str(token_env))
    if token is None:
        raise ConfigError(f"environment variable is not set: {token_env}")
    return token


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
