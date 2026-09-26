"""Runtime-tunable cloud settings (sell-readiness QA: a real Save button).

The inference knobs below are read at process start from env (compose)
with built-in defaults. This module adds a JSON override file so the
Cloud Settings UI can persist choices WITHOUT compose access. On boot,
file values apply only for keys the environment did not set — env always
wins, because the operator's explicit config beats the dashboard.

Every tunable needs a service restart (model/device/FPS are load-time).
The API says so explicitly; the UI must not imply otherwise.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Optional

# Mirrors the Cloud Settings UI sliders exactly (ranges must match).
SETTABLE = {
    "YOLO_MODEL": {"kind": "model"},
    "YOLO_DEVICE": {"kind": "device"},
    "YOLO_CONFIDENCE": {"kind": "float", "min": 0.1, "max": 0.95},
    "INFERENCE_FPS": {"kind": "float", "min": 1, "max": 30},
    "RTSP_TRANSPORT": {"kind": "enum", "values": ("tcp", "udp")},
    "RTSP_TIMEOUT": {"kind": "int", "min": 2, "max": 30},
    "RTSP_RECONNECT_DELAY": {"kind": "float", "min": 0.5, "max": 10.0},
    "SESSION_IDLE_TIMEOUT": {"kind": "int", "min": 30, "max": 300},
}

_DEVICE_RE = re.compile(r"^(cpu|\d+|cuda:\d+)$")


def settings_file_path() -> Path:
    """Override file next to the stations config (created on first save)."""
    return (
        Path(__file__).resolve().parent.parent
        / "config"
        / "cloud_settings.json"
    )


def _clean_value(key: str, value: Any) -> Any:
    spec = SETTABLE[key]
    kind = spec["kind"]
    if kind == "model":
        name = str(value or "").strip()
        if not name.endswith(".pt") or "/" in name or "\\" in name or ".." in name:
            raise ValueError(f"{key} must be a plain .pt filename, got {value!r}")
        return name
    if kind == "device":
        device = str(value or "").strip()
        if not _DEVICE_RE.match(device):
            raise ValueError(f"{key} must be cpu, a GPU index, or cuda:N, got {value!r}")
        return device
    if kind == "enum":
        if value not in spec["values"]:
            raise ValueError(f"{key} must be one of {list(spec['values'])}, got {value!r}")
        return value
    if kind in ("int", "float"):
        try:
            number = int(value) if kind == "int" else float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{key} must be a number, got {value!r}")
        if not (spec["min"] <= number <= spec["max"]):
            raise ValueError(f"{key} must be {spec['min']}..{spec['max']}, got {value!r}")
        return number
    raise ValueError(f"unknown setting kind for {key}")  # pragma: no cover


def validate_settings(values: Mapping[str, Any]) -> dict:
    """Clean a settings payload. Unknown keys and bad values raise ValueError."""
    if not isinstance(values, Mapping):
        raise ValueError("settings payload must be an object")
    cleaned = {}
    for key, value in values.items():
        if key not in SETTABLE:
            raise ValueError(f"Unknown setting: {key}")
        cleaned[key] = _clean_value(key, value)
    return cleaned


def load_overrides(path: Optional[Path | str] = None) -> dict:
    """Read the override file. Missing/corrupt files yield {} (never raise)."""
    try:
        raw = Path(path or settings_file_path()).read_text(encoding="utf-8")
        doc = json.loads(raw)
    except (OSError, ValueError):
        return {}
    if not isinstance(doc, dict):
        return {}
    try:
        return validate_settings(doc)
    except ValueError:
        return {}


def save_overrides(values: Mapping[str, Any], path: Optional[Path | str] = None) -> dict:
    """Validate + persist overrides. Raises ValueError on bad input."""
    cleaned = validate_settings(values)
    target = Path(path or settings_file_path())
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(cleaned, indent=2), encoding="utf-8")
    return cleaned


def apply_overrides(cfg: Any, env: Optional[Mapping[str, str]] = None, path: Optional[Path | str] = None) -> list[str]:
    """Apply file values for keys the environment did not set. Returns applied keys."""
    env = os.environ if env is None else env
    applied = []
    for key, value in load_overrides(path).items():
        if key in env:
            continue
        setattr(cfg, key, value)
        applied.append(key)
    return applied


def current_values(cfg: Any) -> dict:
    """The settable slice of a settings-like object."""
    return {key: getattr(cfg, key, None) for key in SETTABLE}
