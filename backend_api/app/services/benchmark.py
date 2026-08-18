"""De-identified posture benchmark baseline.

Collects the aggregate posture metrics from every recorded session into a
single percentile pool so a plant can answer the most persuasive ergonomics
question: *"your neck-flexion is in the 78th percentile of the N sessions we
have on record."*

Privacy design:
- Only the numeric ``avg_*`` metrics are stored — never worker names,
  employee IDs, session IDs, or timestamps. The baseline file is a list of
  numbers per metric, nothing else, so it can be shown to a prospect without
  exposing anyone's data.
- Rebuilding is idempotent: it scans the session files fresh each time.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]

SESSIONS_DIR = os.environ.get(
    "SESSIONS_DIR",
    os.path.join(str(ROOT), "outputs", "sessions"),
)

BENCHMARK_DIR = os.environ.get(
    "BENCHMARK_DIR",
    os.path.join(str(ROOT), "outputs", "benchmark"),
)
BASELINE_PATH = os.path.join(BENCHMARK_DIR, "baseline.json")

# The aggregate metrics that make sense to compare across sessions/plants.
# Each is a "higher is worse" or "higher is better" angle in degrees; we keep
# the raw distribution and let the frontend phrase the sentence.
BENCHMARK_METRICS = [
    "avg_neck_flexion",
    "avg_trunk_flexion",
    "avg_forward_head_posture",
    "avg_head_tilt_angle",
    "avg_wrist_deviation_angle",
    "avg_shoulder_symmetry",
    "avg_stance_stability",
    "avg_weight_shift_offset",
    "avg_knee_angle",
]

# Labels for the friendly percentile sentences.
METRIC_LABELS = {
    "avg_neck_flexion": "neck flexion",
    "avg_trunk_flexion": "trunk flexion",
    "avg_forward_head_posture": "forward head posture",
    "avg_head_tilt_angle": "head tilt",
    "avg_wrist_deviation_angle": "wrist deviation",
    "avg_shoulder_symmetry": "shoulder symmetry",
    "avg_stance_stability": "stance stability",
    "avg_weight_shift_offset": "weight shift",
    "avg_knee_angle": "knee angle",
}


def _load_session_files() -> list[dict[str, Any]]:
    """Load every session JSON, skipping corrupt files (never raise)."""
    sessions: list[dict[str, Any]] = []
    if not os.path.isdir(SESSIONS_DIR):
        return sessions
    for filename in os.listdir(SESSIONS_DIR):
        if not filename.endswith(".json"):
            continue
        try:
            with open(os.path.join(SESSIONS_DIR, filename), "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                sessions.append(data)
        except (json.JSONDecodeError, OSError):
            logger.warning("benchmark: skipping unreadable session file %s", filename)
            continue
    return sessions


def _metric_value(session: dict[str, Any], metric: str) -> float | None:
    val = session.get(metric)
    try:
        fval = float(val)
    except (TypeError, ValueError):
        return None
    if fval != fval or fval in (float("inf"), float("-inf")):  # NaN / Infinity
        return None
    return fval


def rebuild_baseline() -> dict[str, Any]:
    """Rebuild the percentile pool from all recorded sessions.

    Returns a summary dict; writes ``baseline.json`` with only the numeric
    distributions (no identities, no timestamps).
    """
    sessions = _load_session_files()
    pools: dict[str, list[float]] = {m: [] for m in BENCHMARK_METRICS}
    session_count = 0
    for session in sessions:
        if not session.get("session_id"):
            continue
        has_any = False
        for metric in BENCHMARK_METRICS:
            val = _metric_value(session, metric)
            if val is not None:
                pools[metric].append(val)
                has_any = True
        if has_any:
            session_count += 1

    baseline = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "session_count": session_count,
        "metrics": {m: sorted(vals) for m, vals in pools.items()},
    }
    os.makedirs(BENCHMARK_DIR, exist_ok=True)
    with open(BASELINE_PATH, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2)
    logger.info(
        "benchmark baseline rebuilt: %d sessions, %d metrics",
        session_count, len(BENCHMARK_METRICS),
    )
    return summary_from_baseline(baseline)


def load_baseline() -> dict[str, Any] | None:
    """Load the baseline if it exists; otherwise None (never raise)."""
    if not os.path.exists(BASELINE_PATH):
        return None
    try:
        with open(BASELINE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning("benchmark: baseline file unreadable, rebuild required")
        return None


def summary_from_baseline(baseline: dict[str, Any]) -> dict[str, Any]:
    """Compact summary for the API: per-metric count / min / median / max."""
    metrics = {}
    for metric, values in baseline.get("metrics", {}).items():
        vals = [v for v in values if isinstance(v, (int, float))]
        if not vals:
            metrics[metric] = {"count": 0}
            continue
        n = len(vals)
        mid = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
        metrics[metric] = {
            "count": n,
            "min": round(vals[0], 2),
            "median": round(mid, 2),
            "max": round(vals[-1], 2),
        }
    return {
        "generated_at": baseline.get("generated_at"),
        "session_count": baseline.get("session_count", 0),
        "metrics": metrics,
    }


def percentile_for(metric: str, value: float) -> dict[str, Any]:
    """Percentile rank of *value* within the baseline for *metric*.

    Returns ``{"metric", "label", "value", "percentile", "n", "band"}`` where
    ``band`` is a coarse label (below / near / above typical) and ``n`` is the
    number of sessions the rank is computed against. If the baseline is
    missing or the metric has no data, returns a zeroed record so the UI can
    say "benchmark not built yet".
    """
    out = {
        "metric": metric,
        "label": METRIC_LABELS.get(metric, metric.replace("avg_", "").replace("_", " ")),
        "value": round(float(value), 2),
        "percentile": None,
        "n": 0,
        "band": "no-baseline",
    }
    baseline = load_baseline()
    if baseline is None:
        return out
    vals = [v for v in baseline.get("metrics", {}).get(metric, []) if isinstance(v, (int, float))]
    if not vals:
        return out
    n = len(vals)
    below = sum(1 for v in vals if v <= value)
    pct = (below / n) * 100.0
    out["percentile"] = round(pct, 1)
    out["n"] = n
    if pct >= 75:
        out["band"] = "above-typical"
    elif pct <= 25:
        out["band"] = "below-typical"
    else:
        out["band"] = "typical"
    return out


def ensure_baseline_exists() -> dict[str, Any] | None:
    """Build the baseline on first use if it is missing (never overwrites)."""
    if load_baseline() is None:
        return rebuild_baseline()
    return None
