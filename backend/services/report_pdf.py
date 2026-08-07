"""Server-side PDF export for Risk Trend and Safety reports.

Uses Playwright headless Chromium (shared instance) to render print-optimized HTML
into PDF. The browser is launched once at app startup and reused across requests.

Deployment note: requires `playwright install chromium` after `pip install playwright`.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import Browser, Playwright, async_playwright
    _HAS_PLAYWRIGHT = True
except ImportError:
    Browser = Playwright = async_playwright = None  # type: ignore[assignment]
    _HAS_PLAYWRIGHT = False

_playwright: Optional[Playwright] = None
_browser: Optional[Browser] = None


# ---------------------------------------------------------------------------
# Browser lifecycle
# ---------------------------------------------------------------------------

async def init_browser() -> None:
    """Start Playwright and launch headless Chromium (call from app startup)."""
    global _playwright, _browser
    if not _HAS_PLAYWRIGHT:
        raise RuntimeError("playwright is not installed. Run: pip install playwright && playwright install chromium")
    if _browser is not None:
        return
    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(headless=True)
    logger.info("Playwright Chromium browser launched")


async def close_browser() -> None:
    """Close browser and stop Playwright (call from app shutdown)."""
    global _playwright, _browser
    if _browser is not None:
        try:
            await _browser.close()
        except Exception as e:
            logger.warning("Error closing browser: %s", e)
        _browser = None
    if _playwright is not None:
        try:
            await _playwright.stop()
        except Exception as e:
            logger.warning("Error stopping Playwright: %s", e)
        _playwright = None


async def _get_browser() -> Browser:
    """Return shared browser instance, relaunching if crashed."""
    global _browser
    if _browser is None or not _browser.is_connected():
        logger.info("Browser disconnected — launching new instance")
        await init_browser()
    return _browser


# ---------------------------------------------------------------------------
# Shared CSS
# ---------------------------------------------------------------------------

_CSS = """
@page { margin: 0; }
body {
  font-family: 'Segoe UI', -apple-system, Arial, sans-serif;
  font-size: 10pt;
  line-height: 1.5;
  color: #1e1e1e;
  margin: 0;
  padding: 0;
}
.page-content {
  padding: 20px 40px 30px 40px;
}
h1 { font-size: 18pt; font-weight: 700; color: #0b1d3a; margin: 0 0 4px 0; }
h2 { font-size: 13pt; font-weight: 600; color: #0b1d3a; border-bottom: 1px solid #d0d5dd; padding-bottom: 4px; margin: 20px 0 12px 0; }
.section { margin-bottom: 18px; }
/* KPI grid */
.kpi-grid { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.kpi-card { flex: 1 0 120px; background: #f2f4f7; border-radius: 6px; padding: 10px 14px; text-align: center; }
.kpi-value { font-size: 16pt; font-weight: 700; color: #0b1d3a; }
.kpi-label { font-size: 7.5pt; color: #667085; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }
/* Coverage disclosure */
.disclosure { background: #fffaeb; border: 1px solid #fec84b; border-radius: 6px; padding: 10px 14px; font-size: 8.5pt; color: #b54708; margin: 12px 0; }
/* Info grid */
.info-grid { display: flex; flex-wrap: wrap; gap: 12px; margin: 8px 0; }
.info-item { flex: 1 0 140px; }
.info-label { font-size: 7.5pt; color: #667085; text-transform: uppercase; letter-spacing: 0.3px; }
.info-value { font-size: 10pt; font-weight: 600; color: #1e1e1e; margin-top: 1px; }
/* Stat row (2-column layout) */
.stat-row { display: flex; gap: 12px; margin: 6px 0; }
.stat-col { flex: 1; }
.stat-label { font-size: 7.5pt; color: #667085; }
.stat-value { font-size: 11pt; font-weight: 600; }
/* Bar chart */
.bar-row { display: flex; align-items: center; gap: 8px; margin: 4px 0; }
.bar-label { width: 130px; font-size: 8.5pt; color: #344054; text-align: right; }
.bar-track { flex: 1; height: 18px; background: #e4e7ec; border-radius: 4px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 4px; }
.bar-value { width: 50px; font-size: 8.5pt; font-weight: 600; color: #344054; text-align: right; }
/* Metric trend rows */
.metric-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid #f0f0f0; }
.metric-name { font-size: 9pt; font-weight: 500; }
.metric-average { font-size: 8pt; color: #667085; }
.metric-trend { font-size: 9pt; font-weight: 600; }
/* Top sessions list */
.top-session { display: flex; justify-content: space-between; align-items: center; padding: 5px 8px; background: #f9fafb; border-radius: 4px; margin: 3px 0; }
.top-session-rank { font-size: 8pt; font-weight: 700; color: #98a2b3; width: 24px; }
.top-session-info { flex: 1; }
.top-session-time { font-size: 9pt; font-weight: 500; }
.top-session-risk { font-size: 7pt; font-weight: 700; text-transform: uppercase; }
.top-session-count { font-size: 10pt; font-weight: 700; }
/* Issue row */
.issue-row { display: flex; justify-content: space-between; padding: 4px 8px; background: #f9fafb; border-radius: 4px; margin: 3px 0; }
.issue-name { font-size: 9pt; }
.issue-count { font-size: 9pt; font-weight: 600; color: #667085; }
/* Alert row */
.alert-row { padding: 5px 8px; background: #f9fafb; border-radius: 4px; margin: 3px 0; }
/* Footer / meta */
.meta-line { font-size: 7.5pt; color: #98a3b3; margin-top: 2px; }
.small-note { font-size: 7.5pt; color: #98a3b3; font-style: italic; margin-top: 6px; }
/* Color classes */
.c-green { color: #12b76a; }
.c-orange { color: #f79009; }
.c-red { color: #f04438; }
.c-yellow { color: #d49b00; }
.c-gray { color: #667085; }
.bg-green { background: #12b76a; }
.bg-orange { background: #f79009; }
.bg-red { background: #f04438; }
.bg-yellow { background: #d49b00; }
.bg-blue { background: #2e90fa; }
.bg-purple { background: #7a5af8; }
/* Trend arrows */
.trend-up { color: #12b76a; }
.trend-flat { color: #d49b00; }
.trend-down { color: #f04438; }
/* Watermark — fixed, behind content, repeats on every PDF page */
.watermark {
  position: fixed;
  top: 0; left: 0;
  width: 100%; height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: -1;
  pointer-events: none;
}
.watermark-text {
  font-size: 22pt;
  font-weight: 700;
  color: #000;
  opacity: 0.12;
  transform: rotate(-30deg);
  white-space: nowrap;
  font-family: Arial, Helvetica, sans-serif;
  user-select: none;
}
"""


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

_TREND_ARROW_SVG = {
    "Improving": '<svg width="12" height="12" viewBox="0 0 12 12"><path d="M6 2L2 7h8z" fill="#12b76a"/></svg>',
    "Deteriorating": '<svg width="12" height="12" viewBox="0 0 12 12"><path d="M6 10L2 5h8z" fill="#f04438"/></svg>',
    "Stable": '<svg width="12" height="12" viewBox="0 0 12 12"><rect x="2" y="5" width="8" height="2" rx="1" fill="#d49b00"/></svg>',
}


def _bar_fill(pct: float, color_class: str) -> str:
    """Render a single bar-fill element."""
    return f'<div class="bar-fill {color_class}" style="width:{pct}%"></div>'


def _date_ymd(ts: str) -> str:
    """Convert YYYYMMDD_HHMMSS to YYYY-MM-DD."""
    m = re.match(r"(\d{4})(\d{2})(\d{2})", ts)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ts


def _datetime_display(ts: str) -> str:
    """Convert YYYYMMDD_HHMMSS to readable datetime."""
    m = re.match(r"(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", ts)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}:{m.group(5)}"
    return ts


def _report_id(prefix: str) -> str:
    """Generate a report ID string."""
    now = datetime.now(timezone.utc)
    return f"{prefix}-{now.strftime('%Y%m%d_%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"


def _generated_at() -> str:
    """Current timestamp for display."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ---------------------------------------------------------------------------
# Branded HTML wrapper
# ---------------------------------------------------------------------------

def _branded_html(title: str, body_html: str, report_id: str, generated_at: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>{_CSS}</style>
</head>
<body>
<div class="watermark"><div class="watermark-text">ERGOVIGILANCE \u2014 INTERNAL USE</div></div>
<div class="page-content">
{body_html}
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Risk Trend Report body
# ---------------------------------------------------------------------------

def _risk_trend_body(data: Dict[str, Any]) -> str:
    rd = data["risk_distribution"]
    metrics_html = "".join(
        _metric_row(m) for m in data["metrics"]
    )

    bars = f"""
    <div class="bar-row"><span class="bar-label">LOW</span><div class="bar-track">{_bar_fill(rd['low_pct'], 'bg-green')}</div><span class="bar-value">{rd['low_pct']:.1f}%</span></div>
    <div class="bar-row"><span class="bar-label">MEDIUM</span><div class="bar-track">{_bar_fill(rd['medium_pct'], 'bg-orange')}</div><span class="bar-value">{rd['medium_pct']:.1f}%</span></div>
    <div class="bar-row"><span class="bar-label">HIGH</span><div class="bar-track">{_bar_fill(rd['high_pct'], 'bg-red')}</div><span class="bar-value">{rd['high_pct']:.1f}%</span></div>
    """

    overall_trend_arrow = _TREND_ARROW_SVG.get(data["overall_trend"], "")

    return f"""
<h1>Risk Trend Report</h1>
<div class="meta-line">Report ID: {_report_id('RPT-RISKTREND')} &nbsp;|&nbsp; Generated: {_generated_at()}</div>
<div class="meta-line">{data['total_sessions']} sessions &mdash; {_date_ymd(data['earliest_session'])} to {_date_ymd(data['latest_session'])}</div>

<div class="section">
  <h2>Executive Summary</h2>
  <div class="kpi-grid">
    <div class="kpi-card"><div class="kpi-value">{data['total_sessions']}</div><div class="kpi-label">Sessions</div></div>
    <div class="kpi-card"><div class="kpi-value">{rd['low_pct']:.0f}%</div><div class="kpi-label">Low Risk</div></div>
    <div class="kpi-card"><div class="kpi-value">{rd['medium_pct']:.0f}%</div><div class="kpi-label">Medium Risk</div></div>
    <div class="kpi-card"><div class="kpi-value">{rd['high_pct']:.0f}%</div><div class="kpi-label">High Risk</div></div>
    <div class="kpi-card"><div class="kpi-value">{data['overall_trend']}</div><div class="kpi-label">Overall Trend</div></div>
  </div>
</div>

<div class="section">
  <h2>Risk Distribution (Cross-Session Average)</h2>
  {bars}
  <div class="stat-row">
    <div class="stat-col"><span class="stat-label">Most Common Highest Risk</span><div class="stat-value">{data.get('most_common_highest_risk', 'N/A')}</div></div>
    <div class="stat-col"><span class="stat-label">Most Frequent Issue</span><div class="stat-value">{data.get('most_common_issue', 'None')} ({data.get('most_common_issue_count', 0)})</div></div>
  </div>
</div>

<div class="section">
  <h2>Metric Trends</h2>
  {metrics_html}
</div>

<div class="section">
  <h2>Overall Trend</h2>
  <div style="display:flex;align-items:center;gap:8px;">
    {overall_trend_arrow}
    <span style="font-size:14pt;font-weight:700;">{data['overall_trend']}</span>
  </div>
</div>
"""


def _metric_row(m: Dict[str, Any]) -> str:
    arrow = _TREND_ARROW_SVG.get(m["trend"], "")
    trend_class = {"Improving": "c-green", "Deteriorating": "c-red", "Stable": "c-yellow"}.get(m["trend"], "")
    return f"""
<div class="metric-row">
  <div>
    <div class="metric-name">{m['label']}</div>
    <div class="metric-average">Average: {m['average']:.1f}{m['unit']}</div>
  </div>
  <div style="display:flex;align-items:center;gap:6px;">
    {arrow}
    <span class="metric-trend {trend_class}">{m['trend']}</span>
  </div>
</div>"""


# ---------------------------------------------------------------------------
# Safety Report body
# ---------------------------------------------------------------------------

def _safety_body(data: Dict[str, Any]) -> str:
    d = data

    # Severity bars
    sev_colors = {
        "CRITICAL": ("bg-red", "c-red"),
        "HIGH": ("bg-orange", "c-orange"),
        "MEDIUM": ("bg-yellow", "c-yellow"),
        "WARNING": ("bg-yellow", "c-yellow"),
        "LOW": ("bg-green", "c-green"),
    }
    total_alerts = d["total_alerts"]
    sev_bars = ""
    for sev in ["CRITICAL", "HIGH", "WARNING", "LOW"]:
        count = d["severity_breakdown"].get(sev, 0)
        pct = round(count / total_alerts * 100, 1) if total_alerts > 0 else 0
        bg, _ = sev_colors.get(sev, ("bg-gray", "c-gray"))
        sev_bars += f'<div class="bar-row"><span class="bar-label">{sev}</span><div class="bar-track">{_bar_fill(pct, bg)}</div><span class="bar-value">{count} ({pct}%)</span></div>\n'

    # Trigger rule bars
    trigger_bars = ""
    for t in d["trigger_rule_breakdown"]:
        trigger_bars += f'<div class="bar-row"><span class="bar-label">{t["rule"].replace("_", " ")}</span><div class="bar-track">{_bar_fill(t["pct"], "bg-blue")}</div><span class="bar-value">{t["count"]} ({t["pct"]}%)</span></div>\n'

    # Top sessions (cap at 10)
    top_sessions = d.get("top_sessions_by_alerts", [])[:10]
    top_html = ""
    for i, s in enumerate(top_sessions):
        risk_color_class = {"HIGH": "c-red", "MEDIUM": "c-orange", "LOW": "c-green"}.get(s["highest_risk_level"], "c-gray")
        top_html += f"""
<div class="top-session">
  <span class="top-session-rank">#{i + 1}</span>
  <div class="top-session-info">
    <div class="top-session-time">{_datetime_display(s["session_timestamp"])}</div>
    <div class="top-session-risk {risk_color_class}">{s["highest_risk_level"]} Risk</div>
  </div>
  <span class="top-session-count">{s["alert_count"]}</span>
</div>"""
    if len(d.get("top_sessions_by_alerts", [])) > 10:
        top_html += f'<div class="small-note">Showing top 10 of {d["total_sessions_with_alerts"]} sessions with alerts.</div>'

    # Issues
    issues_html = "".join(
        f'<div class="issue-row"><span class="issue-name">{iss["issue"]}</span><span class="issue-count">{iss["count"]} sessions</span></div>'
        for iss in d["most_frequent_issues"]
    )

    total_monitored_hrs = d["alert_density"]["total_monitored_hours"]
    alerts_per_hour = d["alert_density"]["alerts_per_hour"]
    avg_per_session = d["alert_density"]["avg_per_session"]
    avg_duration_sec = d["alert_density"]["avg_session_duration_seconds"]
    min_a = d["alert_density"]["min_alerts_per_session"]
    max_a = d["alert_density"]["max_alerts_per_session"]

    high_sev = d["high_severity_total"]
    low_sev = d["low_severity_total"]
    high_pct = round(high_sev / total_alerts * 100, 0) if total_alerts > 0 else 0
    low_pct = round(low_sev / total_alerts * 100, 0) if total_alerts > 0 else 0

    return f"""
<h1>Safety Report</h1>
<div class="meta-line">Report ID: {_report_id('RPT-SAFETY')} &nbsp;|&nbsp; Generated: {_generated_at()}</div>
<div class="meta-line">{_date_ymd(d['earliest_session'])} to {_date_ymd(d['latest_session'])}</div>

<div class="disclosure">{d['coverage_statement']}</div>

<div class="section">
  <h2>Executive Summary</h2>
  <div class="kpi-grid">
    <div class="kpi-card"><div class="kpi-value">{d['total_alerts']}</div><div class="kpi-label">Total Alerts</div></div>
    <div class="kpi-card"><div class="kpi-value">{avg_per_session}</div><div class="kpi-label">Avg / Session</div></div>
    <div class="kpi-card"><div class="kpi-value">{alerts_per_hour:.0f}</div><div class="kpi-label">Alerts / Hour</div></div>
    <div class="kpi-card"><div class="kpi-value">{d['total_sessions_with_alerts']}</div><div class="kpi-label">Sessions</div></div>
  </div>
</div>

<div class="section">
  <h2>Severity Breakdown</h2>
  {sev_bars}
  <div class="stat-row">
    <div class="stat-col"><span class="stat-label">CRITICAL + HIGH</span><div class="stat-value c-red">{high_sev} ({high_pct:.0f}%)</div></div>
    <div class="stat-col"><span class="stat-label">WARNING + LOW</span><div class="stat-value c-green">{low_sev} ({low_pct:.0f}%)</div></div>
  </div>
</div>

<div class="section">
  <h2>Trigger Rules</h2>
  {trigger_bars}
</div>

<div class="section">
  <h2>Alert Density</h2>
  <div class="info-grid">
    <div class="info-item"><div class="info-label">Monitor Time</div><div class="info-value">{total_monitored_hrs:.1f} hours</div></div>
    <div class="info-item"><div class="info-label">Avg Duration</div><div class="info-value">{avg_duration_sec}s</div></div>
    <div class="info-item"><div class="info-label">Range / Session</div><div class="info-value">{min_a} &ndash; {max_a}</div></div>
  </div>
</div>

<div class="section">
  <h2>Top Sessions by Alert Count</h2>
  {top_html}
</div>

<div class="section">
  <h2>Most Frequent Issues (Alert Sessions)</h2>
  {issues_html}
</div>
"""


# ---------------------------------------------------------------------------
# Session Report body
# ---------------------------------------------------------------------------

def _session_body(data: Dict[str, Any]) -> str:
    d = data
    rp = d.get("risk_percentages", {})
    ts = d.get("session_timestamp", "")

    # Date display
    date_str = _datetime_display(ts)

    # Duration
    dur_sec = d.get("session_duration_seconds", 0)
    dur_min = dur_sec // 60
    dur_str = f"{dur_min}m {dur_sec % 60}s" if dur_min > 0 else f"{dur_sec}s"

    # Risk bars
    risk_colors = {"LOW": "bg-green", "MEDIUM": "bg-orange", "HIGH": "bg-red"}
    risk_bars = ""
    for level in ["LOW", "MEDIUM", "HIGH"]:
        pct = rp.get(level, 0)
        bg = risk_colors.get(level, "bg-gray")
        risk_bars += f'<div class="bar-row"><span class="bar-label">{level}</span><div class="bar-track">{_bar_fill(pct, bg)}</div><span class="bar-value">{pct:.1f}%</span></div>\n'

    # Feature metrics
    features = [
        ("Neck Flexion", d.get("avg_neck_flexion", 0), "deg"),
        ("Trunk Flexion", d.get("avg_trunk_flexion", 0), "deg"),
        ("Shoulder Symmetry", d.get("avg_shoulder_symmetry", 0), "%"),
        ("Knee Angle", d.get("avg_knee_angle", 0), "deg"),
    ]
    feature_rows = "".join(
        f'<div class="metric-row"><div><div class="metric-name">{name}</div><div class="metric-average">Average: {val:.1f}{unit}</div></div></div>'
        for name, val, unit in features
    )

    # Alert timeline
    alerts = d.get("alerts", [])
    severity_color = {"CRITICAL": "#f04438", "HIGH": "#f79009", "MEDIUM": "#d49b00", "LOW": "#12b76a"}
    alert_rows = ""
    for a in alerts:
        sev = a.get("severity", "LOW")
        color = severity_color.get(sev, "#98a2b3")
        alert_rows += f"""
<div class="alert-row">
  <div style="display:flex;align-items:center;gap:8px;">
    <span style="width:8px;height:8px;border-radius:50%;background:{color};display:inline-block;"></span>
    <div>
      <div style="font-size:9pt;font-weight:500;">{a.get('title', '')} <span style="font-size:7pt;font-weight:700;color:{color};">{sev}</span></div>
      <div style="font-size:7.5pt;color:#667085;">{a.get('message', '')}</div>
      <div style="font-size:7pt;color:#98a2b3;">Frame {a.get('frame_number', '')} &middot; {a.get('created_at', '')} &middot; Rule: {a.get('trigger_rule', '')}</div>
    </div>
  </div>
</div>"""
    if not alert_rows:
        alert_rows = '<div style="font-size:8.5pt;color:#98a2b3;padding:8px 0;">No alerts recorded during this session.</div>'

    issue = d.get("most_frequent_issue")
    issue_str = f"{issue} ({d.get('most_frequent_issue_count', 0)})" if issue else "None"

    return f"""
<h1>Session Report</h1>
<div class="meta-line">Session ID: {d.get('id', 'N/A')} &nbsp;|&nbsp; Generated: {_generated_at()}</div>
<div class="meta-line">{date_str}</div>

<div class="section">
  <h2>Session Metadata</h2>
  <div class="info-grid">
    <div class="info-item"><div class="info-label">Date &amp; Time</div><div class="info-value">{date_str}</div></div>
    <div class="info-item"><div class="info-label">Duration</div><div class="info-value">{dur_str}</div></div>
    <div class="info-item"><div class="info-label">Total Frames</div><div class="info-value">{d.get('total_frames', 0):,}</div></div>
  </div>
</div>

<div class="section">
  <h2>Risk Breakdown</h2>
  {risk_bars}
  <div class="stat-row">
    <div class="stat-col"><span class="stat-label">Highest Risk Level</span><div class="stat-value">{d.get('highest_risk_level', 'N/A')}</div></div>
    <div class="stat-col"><span class="stat-label">Most Frequent Issue</span><div class="stat-value">{issue_str}</div></div>
  </div>
</div>

<div class="section">
  <h2>Average Ergonomic Features</h2>
  {feature_rows}
</div>

<div class="section">
  <h2>Alert Timeline ({len(alerts)} alert{'s' if len(alerts) != 1 else ''})</h2>
  {alert_rows}
</div>
"""


# ---------------------------------------------------------------------------
# Worker Trends Report body
# ---------------------------------------------------------------------------

def _worker_trends_body(data: Dict[str, Any]) -> str:
    d = data
    workers = d.get("workers", [])
    departments = d.get("departments", [])
    temporal = d.get("temporal_curves", [])
    stations = d.get("station_analysis", [])

    # Worker rows
    worker_rows = ""
    for w in workers:
        risk_class = "c-red" if w["avg_risk_score"] >= 70 else "c-orange" if w["avg_risk_score"] >= 40 else "c-green"
        trend_class = {"improving": "c-green", "deteriorating": "c-red"}.get(w["trend"], "c-yellow")
        arrow = _TREND_ARROW_SVG.get(w["trend"].capitalize(), "")
        worker_rows += f"""
<div class="metric-row">
  <div>
    <div class="metric-name">{w['name']} <span style="font-weight:normal;color:#64748b;font-size:11px;">({w['department']}, {w['shift']}, {w['sessions']} sessions)</span></div>
  </div>
  <div style="display:flex;align-items:center;gap:10px;">
    <span class="{risk_class}" style="font-weight:700;">{w['avg_risk_score']:.1f}</span>
    <span style="font-size:10px;padding:2px 6px;border-radius:4px;background:{"#fef2f2" if w['latest_risk_level'] == "HIGH" else "#fff7ed" if w['latest_risk_level'] == "MEDIUM" else "#f0fdf4"};color:{"#dc2626" if w['latest_risk_level'] == "HIGH" else "#ea580c" if w['latest_risk_level'] == "MEDIUM" else "#16a34a"};font-weight:700;">{w['latest_risk_level']}</span>
    <span style="display:flex;align-items:center;gap:4px;">{arrow}<span class="{trend_class}">{w['trend'].capitalize()}</span></span>
  </div>
</div>"""

    # Department rows
    dept_rows = ""
    for dp in departments:
        risk_class = "c-red" if dp["avg_risk_score"] >= 70 else "c-orange" if dp["avg_risk_score"] >= 40 else "c-green"
        trend_class = {"improving": "c-green", "deteriorating": "c-red"}.get(dp["trend"], "c-yellow")
        arrow = _TREND_ARROW_SVG.get(dp["trend"].capitalize(), "")
        dept_rows += f"""
<div class="metric-row">
  <div>
    <div class="metric-name">{dp['department']}</div>
    <div style="font-size:11px;color:#64748b;">{dp['worker_count']} worker{'s' if dp['worker_count'] != 1 else ''}</div>
  </div>
  <div style="display:flex;align-items:center;gap:10px;">
    <span class="{risk_class}" style="font-weight:700;">{dp['avg_risk_score']:.1f}</span>
    {f'<span style="font-size:10px;padding:2px 6px;border-radius:4px;background:#fef2f2;color:#dc2626;font-weight:700;">{dp["high_risk_count"]} HIGH</span>' if dp['high_risk_count'] > 0 else ''}
    <span style="display:flex;align-items:center;gap:4px;">{arrow}<span class="{trend_class}">{dp['trend'].capitalize()}</span></span>
  </div>
</div>"""

    # Temporal curves (weekly risk bars)
    temporal_html = ""
    for curve in temporal:
        bars = ""
        for pt in curve["points"]:
            height = max(8, int(pt["avg_risk_score"] / 100 * 60))
            color = "#dc2626" if pt["avg_risk_score"] >= 70 else "#ea580c" if pt["avg_risk_score"] >= 40 else "#16a34a"
            bars += f'<div style="display:flex;flex-direction:column;align-items:center;flex:1;min-width:0;"><span style="font-size:9px;color:#64748b;">{pt["avg_risk_score"]:.0f}</span><div style="width:100%;height:{height}px;background:{color};border-radius:3px 3px 0 0;margin-top:2px;"></div><span style="font-size:8px;color:#94a3b8;margin-top:2px;">{pt["week"]}</span></div>'
        temporal_html += f"""
<div style="margin-bottom:16px;">
  <div style="font-size:12px;font-weight:600;margin-bottom:4px;">{curve['name']} <span style="font-weight:normal;color:#64748b;">({curve['department']})</span></div>
  <div style="display:flex;align-items-end;gap:4px;height:70px;">{bars}</div>
</div>"""

    # Station rows
    station_rows = ""
    for st in stations:
        risk_class = "c-red" if st["avg_risk_score"] >= 70 else "c-orange" if st["avg_risk_score"] >= 40 else "c-green"
        station_rows += f"""
<div class="metric-row">
  <div>
    <div class="metric-name">{st['display_name']}</div>
    <div style="font-size:11px;color:#64748b;">{st['sessions']} sessions, {st['worker_count']} worker{'s' if st['worker_count'] != 1 else ''}</div>
  </div>
  <div style="display:flex;align-items:center;gap:10px;">
    <span class="{risk_class}" style="font-weight:700;">{st['avg_risk_score']:.1f}</span>
    {f'<span style="font-size:10px;padding:2px 6px;border-radius:4px;background:#fef2f2;color:#dc2626;font-weight:700;">{st["high_risk_count"]} HIGH</span>' if st['high_risk_count'] > 0 else ''}
  </div>
</div>"""

    return f"""
<h1>Worker Trends Report</h1>
<div class="meta-line">Report ID: {_report_id('RPT-WORKER')} &nbsp;|&nbsp; Generated: {_generated_at()}</div>
<div class="meta-line">{d['total_workers_with_data']} of {d['total_workers']} workers with session data &mdash; {len(departments)} departments &mdash; {len(stations)} stations</div>

<div class="section">
  <h2>Department Patterns</h2>
  {dept_rows if dept_rows else '<div style="font-size:12px;color:#64748b;">No department data available.</div>'}
</div>

<div class="section">
  <h2>Worker Details</h2>
  {worker_rows if worker_rows else '<div style="font-size:12px;color:#64748b;">No worker data available.</div>'}
</div>

{"<div class='section'><h2>Weekly Risk Trends</h2>" + temporal_html + "</div>" if temporal_html else ""}

{"<div class='section'><h2>Station Risk Patterns</h2>" + station_rows + "</div>" if station_rows else ""}
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def render_risk_trend_pdf(data: Dict[str, Any]) -> bytes:
    """Render a Risk Trend Report PDF from pre-computed data dict."""
    html = _branded_html("Risk Trend Report", _risk_trend_body(data), "", "")
    return await _render_pdf(html)


async def render_safety_report_pdf(data: Dict[str, Any]) -> bytes:
    """Render a Safety Report PDF from pre-computed data dict."""
    html = _branded_html("Safety Report", _safety_body(data), "", "")
    return await _render_pdf(html)


async def render_session_pdf(data: Dict[str, Any]) -> bytes:
    """Render a single Session Report PDF from the session detail dict."""
    html = _branded_html("Session Report", _session_body(data), "", "")
    return await _render_pdf(html)


async def render_worker_trends_pdf(data: Dict[str, Any]) -> bytes:
    """Render a Worker Trends Report PDF from pre-computed data dict."""
    html = _branded_html("Worker Trends Report", _worker_trends_body(data), "", "")
    return await _render_pdf(html)


async def _render_pdf(html: str) -> bytes:
    """Render HTML to PDF bytes using the shared Playwright browser."""
    browser = await _get_browser()
    context = await browser.new_context()
    page = await context.new_page()
    try:
        await page.set_content(html, wait_until="networkidle")
        pdf_bytes = await page.pdf(
            format="A4",
            print_background=True,
            display_header_footer=True,
            header_template="",
            footer_template=(
                '<div style="font-size:7.5pt;color:#98a3b3;padding:2px 40px 6px 40px;'
                'width:100%;text-align:center;">'
                'Page <span class="pageNumber"></span> of <span class="totalPages"></span>'
                "</div>"
            ),
            margin={"top": "0.65in", "bottom": "0.65in", "left": "0.6in", "right": "0.6in"},
        )
        return pdf_bytes
    finally:
        await page.close()
        await context.close()
