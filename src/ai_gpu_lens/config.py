from __future__ import annotations

from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    pass


def load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        import json

        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ConfigError("config file must contain a mapping")
        return payload
    return parse_simple_yaml(text)


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the small YAML subset ai-gpu-lens uses for config files."""

    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if ":" not in stripped:
            raise ConfigError(f"line {line_no}: expected key: value")
        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if not key:
            raise ConfigError(f"line {line_no}: empty key")
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise ConfigError(f"line {line_no}: invalid indentation")
        parent = stack[-1][1]
        if raw_value == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = parse_scalar(raw_value)
    return root


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"''", '""'}:
        return ""
    if (
        len(value) >= 2
        and value[0] == value[-1]
        and value[0] in {"'", '"'}
    ):
        return value[1:-1]
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "~"}:
        return None
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def get_config_value(config: dict[str, Any], name: str, default: Any = None) -> Any:
    return config.get(name, config.get(name.replace("_", "-"), default))


def parse_gpu_prices(values: list[str] | None) -> dict[str, float]:
    prices: dict[str, float] = {}
    for value in values or []:
        if "=" not in value:
            raise ConfigError(f"GPU price must be MODEL=PRICE, got: {value}")
        model, raw_price = value.split("=", 1)
        model = model.strip()
        if not model:
            raise ConfigError("GPU price model cannot be empty")
        try:
            prices[model] = float(raw_price.strip())
        except ValueError as exc:
            raise ConfigError(f"GPU price must be numeric: {value}") from exc
    return prices


def normalize_gpu_prices(value: Any) -> dict[str, float]:
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise ConfigError("gpu_prices must be a mapping")
    prices: dict[str, float] = {}
    for model, raw_price in value.items():
        try:
            prices[str(model)] = float(raw_price)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"GPU price for {model!r} must be numeric") from exc
    return prices


def config_path(value: Any) -> Path | None:
    if value in (None, ""):
        return None
    return Path(str(value))
