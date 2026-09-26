"""Assessment report pack builder (sell-readiness N3c).

Builds the per-tier deliverable payloads sold in
``docs/ASSESSMENT_PRICING.md`` — top-3 risks, station comparison,
benchmark percentiles, RULA/REBA summary — from session/alert data,
feeding the existing PDF renderers in ``report_pdf.py``.

Pure data shaping: no browser, no DB, no network. Fully unit-tested.
Severity rank is HIGH > MEDIUM > LOW; ties break by count, then name
(deterministic output for identical inputs).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

ASSESSMENT_TIERS = ("rapid", "line", "baseline")

_SEVERITY_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

SCREENING_NOTE = (
    "AI-assisted ergonomic screening aid, not a medical device. "
    "Figures describe observed alerts, not certified injury risk."
)


def top_risks(alerts: list[dict], n: int = 3) -> list[dict]:
    """Rank (severity, task) pairs — the 'top-3 risks' deliverable."""
    counts: dict[tuple[str, str]] = {}
    for alert in alerts or []:
        severity = str(alert.get("severity", "LOW")).upper()
        task = str(alert.get("task", "unknown"))
        key = (severity, task)
        counts[key] = counts.get(key, 0) + 1
    ranked = sorted(
        counts.items(),
        key=lambda item: (_SEVERITY_RANK.get(item[0][0], 3), -item[1], item[0][1]),
    )
    total = sum(counts.values())
    return [
        {
            "severity": severity,
            "task": task,
            "count": count,
            "share": round(count / total, 3) if total else 0.0,
        }
        for (severity, task), count in ranked[: max(n, 0)]
    ]


def station_comparison(sessions: list[dict]) -> list[dict]:
    """Per-station rollup: sessions, alerts, alerts/hour, worst severity."""
    stats: dict[str, dict] = {}
    for session in sessions or []:
        station = str(session.get("station", "unknown"))
        entry = stats.setdefault(
            station, {"sessions": 0, "minutes": 0.0, "alerts": 0, "worst": "LOW"}
        )
        entry["sessions"] += 1
        try:
            entry["minutes"] += float(session.get("duration_min", 0) or 0)
        except (TypeError, ValueError):
            pass
        alerts = session.get("alerts") or []
        entry["alerts"] += len(alerts)
        for alert in alerts:
            severity = str(alert.get("severity", "LOW")).upper()
            if _SEVERITY_RANK.get(severity, 3) < _SEVERITY_RANK.get(entry["worst"], 3):
                entry["worst"] = severity
    rows = []
    for station in sorted(stats):
        entry = stats[station]
        hours = entry["minutes"] / 60.0
        rows.append(
            {
                "station": station,
                "sessions": entry["sessions"],
                "alerts": entry["alerts"],
                "alerts_per_hour": round(entry["alerts"] / hours, 2) if hours > 0 else 0.0,
                "worst_severity": entry["worst"],
            }
        )
    return rows


def benchmark_percentiles(station_rates: dict[str, float], baseline: list[float]) -> list[dict]:
    """Percentile rank of each station's alert rate vs. a baseline sample.

    Percentile = share of baseline values at or below the station rate.
    Empty baseline yields None (honest gap, not a fabricated benchmark).
    """
    rows = []
    for station in sorted(station_rates):
        rate = station_rates[station]
        if not baseline:
            pct = None
        else:
            at_or_below = sum(1 for value in baseline if value <= rate)
            pct = round(100.0 * at_or_below / len(baseline), 1)
        rows.append({"station": station, "alerts_per_hour": rate, "percentile": pct})
    return rows


def build_pack(
    tier: str,
    sessions: Optional[list[dict]] = None,
    alerts: Optional[list[dict]] = None,
    baseline_rates: Optional[list[float]] = None,
) -> dict:
    """Assemble a tier's deliverable payload. Raises ValueError on bad tier."""
    if tier not in ASSESSMENT_TIERS:
        raise ValueError(f"Unknown assessment tier: {tier}")
    sessions = sessions or []
    alerts = alerts or []
    comparison = station_comparison(sessions)
    pack: dict[str, Any] = {
        "tier": tier,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "top_risks": top_risks(alerts),
        "station_comparison": comparison,
        "screening_note": SCREENING_NOTE,
    }
    if tier in ("line", "baseline"):
        rates = {row["station"]: row["alerts_per_hour"] for row in comparison}
        pack["benchmarks"] = benchmark_percentiles(rates, baseline_rates or [])
    return pack
