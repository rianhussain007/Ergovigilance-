"""Train the predictive risk forecaster on real timeline data.

Builds two forecasting models from the persisted session timelines
(Postgres when DATABASE_URL is set, else JSON files):

1. **Next-window model** — from the last ``window_frames`` frames of a
   session, predict the mean risk over the following ``horizon_frames``.
   Sliding windows over all sessions yield tens of thousands of training
   rows from the ~60k frame dataset.

2. **Early-session model** — from the first ``early_fraction`` of a session,
   predict the full-session mean risk. One row per session (fewer rows, so
   this model carries a lower-confidence caveat).

Output bundle (models/risk_forecaster.pkl):
    {model, feature_columns, metrics, config, purpose}

Usage:
    DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/ergovigilance \
        python scripts/train_risk_forecaster.py
    python scripts/train_risk_forecaster.py --out models/risk_forecaster.pkl
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND_API_DIR = ROOT / "backend_api"
if str(BACKEND_API_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_API_DIR))

from backend.services.predictive import (  # noqa: E402
    WINDOW_FEATURES,
    extract_window_features,
)


def _load_session_timelines() -> list[tuple[dict, list[dict]]]:
    """Load (payload, frames) pairs from Postgres or files."""
    try:
        from app.core.postgres import pg_enabled, fetch_sessions, fetch_frames
        if pg_enabled():
            sessions = fetch_sessions()
            pairs = []
            for s in sessions:
                sid = s.get("session_id")
                if not sid:
                    continue
                frames = fetch_frames(sid)
                if frames:
                    pairs.append((s, frames))
            print(f"Loaded {len(pairs)} sessions from Postgres")
            return pairs
    except Exception as exc:
        print(f"Postgres load failed ({exc}) — falling back to files")
    from app.core.postgres import iter_timeline_files
    pairs = [(p, f) for p, f in iter_timeline_files(str(ROOT)) if f]
    print(f"Loaded {len(pairs)} sessions from JSON files")
    return pairs


def build_next_window_dataset(pairs, window_frames: int, horizon_frames: int, stride: int = 20):
    """Sliding-window rows: features from window -> target = mean risk of horizon."""
    X, y = [], []
    skipped = 0
    for _, frames in pairs:
        n = len(frames)
        for start in range(0, n - window_frames - horizon_frames, stride):
            window = frames[start:start + window_frames]
            horizon = frames[start + window_frames: start + window_frames + horizon_frames]
            if len(window) < window_frames or len(horizon) < horizon_frames:
                continue
            X.append(extract_window_features(window))
            horizon_risks = [f.get("risk_score") for f in horizon]
            horizon_risks = [r for r in horizon_risks if isinstance(r, (int, float)) and r == r]
            if not horizon_risks:
                skipped += 1
                continue
            y.append(float(np.mean(horizon_risks)))
    return np.asarray(X, dtype=float), np.asarray(y, dtype=float), skipped


def build_early_session_dataset(pairs, early_fraction: float, min_frames: int = 30):
    """One row per session: first-portion features -> full-session mean risk."""
    X, y, ids = [], [], []
    skipped = 0
    for payload, frames in pairs:
        n = len(frames)
        if n < min_frames:
            skipped += 1
            continue
        early_n = max(min_frames, int(n * early_fraction))
        early = frames[:early_n]
        full_risks = [f.get("risk_score") for f in frames]
        full_risks = [r for r in full_risks if isinstance(r, (int, float)) and r == r]
        if len(full_risks) < min_frames:
            skipped += 1
            continue
        X.append(extract_window_features(early))
        y.append(float(np.mean(full_risks)))
        ids.append(payload.get("session_id", ""))
    return np.asarray(X, dtype=float), np.asarray(y, dtype=float), ids, skipped


def train(out: Path, window_frames: int, horizon_frames: int, early_fraction: float, seed: int) -> dict:
    pairs = _load_session_timelines()
    print(f"Total sessions with timelines: {len(pairs)}")

    # ── Next-window model ─────────────────────────────────────────
    X_nw, y_nw, skipped_nw = build_next_window_dataset(
        pairs, window_frames, horizon_frames)
    print(f"Next-window rows: {len(X_nw)} (skipped {skipped_nw})")
    metrics_nw: dict = {}
    if len(X_nw) >= 200:
        X_tr, X_te, y_tr, y_te = train_test_split(
            X_nw, y_nw, test_size=0.2, random_state=seed)
        m = HistGradientBoostingRegressor(
            max_iter=200, learning_rate=0.08, max_depth=4,
            min_samples_leaf=20, random_state=seed,
        )
        m.fit(X_tr, y_tr)
        preds = m.predict(X_te)
        metrics_nw = {
            "mae": round(float(mean_absolute_error(y_te, preds)), 2),
            "r2": round(float(r2_score(y_te, preds)), 3),
            "rows": int(len(X_nw)),
            "window_frames": window_frames,
            "horizon_frames": horizon_frames,
        }
        print(f"Next-window holdout: MAE={metrics_nw['mae']} R2={metrics_nw['r2']}")
    else:
        m = None
        print("Not enough next-window rows — next-window model disabled")

    # ── Early-session model ───────────────────────────────────────
    X_es, y_es, ids_es, skipped_es = build_early_session_dataset(pairs, early_fraction)
    print(f"Early-session rows: {len(X_es)} (skipped {skipped_es})")
    metrics_es: dict = {}
    if len(X_es) >= 20:
        X_tr, X_te, y_tr, y_te = train_test_split(
            X_es, y_es, test_size=0.25, random_state=seed)
        m_es = HistGradientBoostingRegressor(
            max_iter=150, learning_rate=0.08, max_depth=3,
            min_samples_leaf=2, random_state=seed,
        )
        m_es.fit(X_tr, y_tr)
        preds = m_es.predict(X_te)
        metrics_es = {
            "mae": round(float(mean_absolute_error(y_te, preds)), 2),
            "r2": round(float(r2_score(y_te, preds)), 3),
            "rows": int(len(X_es)),
            "early_fraction": early_fraction,
        }
        print(f"Early-session holdout: MAE={metrics_es['mae']} R2={metrics_es['r2']}")
    else:
        m_es = None
        print("Not enough early-session rows — early-session model disabled")

    if m is None and m_es is None:
        raise RuntimeError("No usable training rows — nothing to save")

    # Prefer the next-window model as the primary regressor (it is trained on
    # far more data); the early-session model rides along in the bundle for
    # the Analytics card and can be promoted later with more sessions.
    primary = m if m is not None else m_es
    bundle = {
        "model": primary,
        "feature_columns": WINDOW_FEATURES,
        "metrics": {"next_window": metrics_nw, "early_session": metrics_es},
        "config": {
            "window_frames": window_frames,
            "horizon_frames": horizon_frames,
            "early_fraction": early_fraction,
            "confidence_threshold": 0.45,
        },
        "purpose": (
            "Predictive risk forecaster — next-window + early-session mean "
            "risk regression. Advisory only; the rule-based Context Engine "
            "stays authoritative."
        ),
        "trained_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, out)
    print(f"model saved: {out}")
    return bundle


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "models/risk_forecaster.pkl")
    ap.add_argument("--window-frames", type=int, default=150)   # ~10s at 15fps
    ap.add_argument("--horizon-frames", type=int, default=150)  # next ~10s
    ap.add_argument("--early-fraction", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    train(args.out, args.window_frames, args.horizon_frames, args.early_fraction, args.seed)
