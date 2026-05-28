from __future__ import annotations

import argparse
import getpass
import json
import os
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
from .i18n import SUPPORTED_LANGUAGES, normalize_language, t
from .doctor import render_doctor_text, run_doctor
from .prometheus import (
    DEFAULT_GPU_UTIL_QUERY,
    DEFAULT_KUBE_GPU_REQUEST_QUERY,
    DEFAULT_MEMORY_TOTAL_QUERY,
    DEFAULT_MEMORY_USED_QUERY,
    PrometheusError,
    collect_bundle,
    load_bundle,
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
    if options["from_file"]:
        bundle = load_bundle(options["from_file"])
    else:
        try:
            bundle = collect_bundle(
                options["prometheus_url"],
                hours=options["hours"],
                step=options["step"],
                gpu_util_query=options["gpu_util_query"],
                memory_used_query=options["memory_used_query"],
                memory_total_query=options["memory_total_query"],
                kube_gpu_request_query=options["kube_gpu_request_query"],
                timeout=options["timeout"],
                basic_auth=options["basic_auth"],
                bearer_token=options["bearer_token"],
            )
        except PrometheusError as exc:
            print(f"error: {exc}")
            return 2

    report = analyze_bundle(
        bundle,
        window_hours=options["hours"],
        step=options["step"],
        price_per_gpu_hour=options["price_per_gpu_hour"],
        gpu_prices=options["gpu_prices"],
        idle_threshold=options["idle_threshold"],
        active_threshold=options["active_threshold"],
        language=language,
    )
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
