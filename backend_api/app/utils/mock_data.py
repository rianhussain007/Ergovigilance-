"""Mock data — exact JSON contracts expected by the React frontend.

Every dictionary here matches the Pydantic schemas in app/schemas/api.py
and the TypeScript interfaces in src/types/api.ts.
"""

from datetime import datetime, timezone

_NOW = datetime.now(timezone.utc)
_TS = _NOW.strftime("%Y-%m-%dT%H:%M:%SZ")

# ---------------------------------------------------------------------------
# DashboardResponse — matches React's DashboardResponse interface
# ---------------------------------------------------------------------------

DASHBOARD = {
    "session": {
        "id": "SESH-2026-06-30-001",
        "workerName": "Marcus Thorne",
        "workerId": "WA-4092",
        "startTime": "2026-06-30T08:00:00Z",
        "currentTime": _TS,
        "duration": 23400,
        "framesAnalyzed": 18420,
        "cameraStatus": "active",
    },
    "liveStatus": {
        "riskLevel": "moderate",
        "riskScore": 42.0,
        "confidence": 94.2,
        "currentTask": "Assembly Line B - Component Fitting",
        "workerStatus": "active",
    },
    "ergonomicFeatures": [
        {"id": "neck_flexion", "name": "Neck Flexion", "value": 18.0, "unit": "deg", "min": 0.0, "max": 60.0, "status": "moderate"},
        {"id": "trunk_flexion", "name": "Trunk Flexion", "value": 22.0, "unit": "deg", "min": 0.0, "max": 60.0, "status": "moderate"},
        {"id": "shoulder_elevation", "name": "Shoulder Elevation", "value": 12.0, "unit": "deg", "min": 0.0, "max": 45.0, "status": "low"},
        {"id": "shoulder_symmetry", "name": "Shoulder Symmetry", "value": 8.0, "unit": "deg", "min": 0.0, "max": 30.0, "status": "low"},
        {"id": "alignment_deviation", "name": "Alignment Deviation", "value": 4.0, "unit": "cm", "min": 0.0, "max": 15.0, "status": "low"},
        {"id": "knee_angle", "name": "Knee Angle", "value": 142.0, "unit": "deg", "min": 90.0, "max": 180.0, "status": "good"},
    ],
    "issues": [
        {"id": "ISS-001", "severity": "high", "name": "Sustained Neck Flexion >30\u00b0", "timestamp": "2026-06-30T14:22:01Z", "detail": "Zone C - Assembly. Neck flexion exceeded 30\u00b0 threshold for 4.2s."},
        {"id": "ISS-002", "severity": "moderate", "name": "Trunk Asymmetry During Lift", "timestamp": "2026-06-30T14:18:45Z", "detail": "Zone B - Inspection. Trunk rotated 15\u00b0 off midline during load lift."},
        {"id": "ISS-003", "severity": "moderate", "name": "Shoulder Elevation Spike", "timestamp": "2026-06-30T14:15:30Z", "detail": "Zone A - Assembly. Right shoulder elevation exceeded 25\u00b0 during overhead reach."},
        {"id": "ISS-004", "severity": "low", "name": "Minor Wrist Deviation", "timestamp": "2026-06-30T14:10:12Z", "detail": "Zone C - Packaging. Wrist deviation of 12\u00b0 detected during repetitive motion."},
    ],
    "recommendations": {
        "worker": "Adjust workstation height by lowering chair 5cm to reduce neck flexion. Take a micro-break every 25 minutes for shoulder relaxation.",
        "supervisor": "Schedule ergonomic assessment for Marcus. Consider task rotation between Station B and Station C every 2 hours to reduce repetitive strain.",
    },
    "sessionAnalytics": {
        "sessionDuration": "6h 30m",
        "framesAnalyzed": 18420,
        "highestRisk": "Neck Flexion",
        "mostFrequentIssue": "Trunk Asymmetry",
        "averageNeck": 16.4,
        "averageTrunk": 20.1,
        "averageKnee": 145.2,
    },
    "riskHistory": [
        {"time": "08:00", "value": 15.0},
        {"time": "08:30", "value": 22.0},
        {"time": "09:00", "value": 18.0},
        {"time": "09:30", "value": 35.0},
        {"time": "10:00", "value": 28.0},
        {"time": "10:30", "value": 42.0},
        {"time": "11:00", "value": 38.0},
        {"time": "11:30", "value": 45.0},
        {"time": "12:00", "value": 30.0},
        {"time": "12:30", "value": 25.0},
        {"time": "13:00", "value": 33.0},
        {"time": "13:30", "value": 40.0},
        {"time": "14:00", "value": 42.0},
        {"time": "14:30", "value": 38.0},
    ],
    "trendAnalysis": {
        "trend": "stable",
        "averageRisk": 32.4,
        "sessionsAnalyzed": 128,
        "improving": 45,
        "stable": 62,
        "deteriorating": 21,
    },
}

# ---------------------------------------------------------------------------
# Sessions — matches React's SessionRecord[]
# ---------------------------------------------------------------------------

SESSIONS = [
    {"id": "SESH-2026-06-30-001", "date": "2026-06-30", "duration": "6h 30m", "highestRisk": "Neck Flexion", "task": "Assembly Line B", "status": "active"},
    {"id": "SESH-2026-06-29-003", "date": "2026-06-29", "duration": "8h 12m", "highestRisk": "Trunk Flexion", "task": "Loading Dock", "status": "completed"},
    {"id": "SESH-2026-06-29-002", "date": "2026-06-29", "duration": "4h 00m", "highestRisk": "Shoulder Elevation", "task": "Quality Control", "status": "completed"},
    {"id": "SESH-2026-06-29-001", "date": "2026-06-29", "duration": "7h 45m", "highestRisk": "Knee Angle", "task": "Fabrication", "status": "completed"},
    {"id": "SESH-2026-06-28-005", "date": "2026-06-28", "duration": "6h 20m", "highestRisk": "Neck Flexion", "task": "Assembly Line A", "status": "completed"},
    {"id": "SESH-2026-06-28-004", "date": "2026-06-28", "duration": "8h 00m", "highestRisk": "Trunk Flexion", "task": "Packaging", "status": "completed"},
    {"id": "SESH-2026-06-28-003", "date": "2026-06-28", "duration": "5h 30m", "highestRisk": "Shoulder Symmetry", "task": "Assembly Line B", "status": "completed"},
    {"id": "SESH-2026-06-28-002", "date": "2026-06-28", "duration": "3h 15m", "highestRisk": "Alignment Deviation", "task": "Inspection", "status": "interrupted"},
    {"id": "SESH-2026-06-28-001", "date": "2026-06-28", "duration": "7h 50m", "highestRisk": "Neck Flexion", "task": "Assembly Line A", "status": "completed"},
    {"id": "SESH-2026-06-27-002", "date": "2026-06-27", "duration": "8h 05m", "highestRisk": "Trunk Flexion", "task": "Loading Dock", "status": "completed"},
]

# ---------------------------------------------------------------------------
# Trends — matches React's TrendResponse
# ---------------------------------------------------------------------------

TRENDS = {
    "weeklyTrend": [
        {"week": "W22", "averageRisk": 38.2, "sessions": 18, "incidents": 12},
        {"week": "W23", "averageRisk": 35.7, "sessions": 21, "incidents": 10},
        {"week": "W24", "averageRisk": 32.4, "sessions": 19, "incidents": 8},
        {"week": "W25", "averageRisk": 36.1, "sessions": 22, "incidents": 11},
        {"week": "W26", "averageRisk": 33.8, "sessions": 20, "incidents": 9},
        {"week": "W27", "averageRisk": 31.2, "sessions": 23, "incidents": 7},
        {"week": "W28", "averageRisk": 29.5, "sessions": 25, "incidents": 6},
        {"week": "W29", "averageRisk": 32.4, "sessions": 20, "incidents": 9},
    ],
    "featureTrends": [
        {"feature": "Neck Flexion", "current": 18.0, "previous": 22.0, "change": -18.2},
        {"feature": "Trunk Flexion", "current": 22.0, "previous": 25.0, "change": -12.0},
        {"feature": "Shoulder Elevation", "current": 12.0, "previous": 15.0, "change": -20.0},
        {"feature": "Shoulder Symmetry", "current": 8.0, "previous": 10.0, "change": -20.0},
        {"feature": "Alignment Deviation", "current": 4.0, "previous": 6.0, "change": -33.3},
        {"feature": "Knee Angle", "current": 142.0, "previous": 138.0, "change": 2.9},
    ],
    "riskDistribution": {
        "low": 112,
        "moderate": 18,
        "high": 12,
    },
}

# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

REPORTS = [
    {"id": 1, "title": "Safety Report \u2014 June 2026", "type": "Safety", "date": "2026-06-30", "size": "2.4 MB"},
    {"id": 2, "title": "Trend Report \u2014 Week 29", "type": "Trend", "date": "2026-06-28", "size": "1.8 MB"},
    {"id": 3, "title": "Session Export \u2014 SESH-001", "type": "Session", "date": "2026-06-30", "size": "4.2 MB"},
    {"id": 4, "title": "Monthly Summary \u2014 June", "type": "Summary", "date": "2026-06-30", "size": "3.1 MB"},
    {"id": 5, "title": "CSV \u2014 Raw Telemetry", "type": "Data", "date": "2026-06-29", "size": "12.6 MB"},
]

# ---------------------------------------------------------------------------
# Cameras
# ---------------------------------------------------------------------------

CAMERAS = [
    {"id": "CAM-001", "name": "Assembly Line A \u2014 Station 1", "worker": "Marcus Thorne", "fps": 30, "risk": "moderate", "recording": True, "uptime": "12h 34m"},
    {"id": "CAM-002", "name": "Assembly Line B \u2014 Station 3", "worker": "Chen Wei", "fps": 28, "risk": "low", "recording": True, "uptime": "8h 12m"},
    {"id": "CAM-003", "name": "Loading Dock \u2014 Bay 2", "worker": "James Kowalski", "fps": 30, "risk": "high", "recording": True, "uptime": "6h 45m"},
    {"id": "CAM-004", "name": "Quality Control \u2014 Table 3", "worker": "Priya Sharma", "fps": 25, "risk": "low", "recording": False, "uptime": "4h 20m"},
    {"id": "CAM-005", "name": "Fabrication \u2014 Welding Bay", "worker": "Sarah Jenkins", "fps": 30, "risk": "high", "recording": True, "uptime": "10h 05m"},
    {"id": "CAM-006", "name": "Packaging \u2014 Line 2", "worker": "Maria Santos", "fps": 27, "risk": "moderate", "recording": True, "uptime": "7h 30m"},
]

# ---------------------------------------------------------------------------
# Workstations — matches React's DeploymentCenter workstations
# ---------------------------------------------------------------------------

WORKSTATIONS = [
    {"id": "A1", "name": "Workstation A1", "worker": "Marcus Thorne", "task": "Component Fitting", "risk": "moderate", "healthScore": 72, "camera": "CAM-001", "connected": True, "neckAngle": 22.0, "trunkAngle": 18.0, "shoulderAngle": 14.0, "kneeAngle": 142.0, "issues": ["Sustained neck flexion >20\u00b0", "Trunk asymmetry during lift"], "recommendation": "Lower component tray by 10cm. Take micro-break every 25min."},
    {"id": "A2", "name": "Workstation A2", "worker": "Elena Rodriguez", "task": "Data Entry", "risk": "low", "healthScore": 88, "camera": "CAM-001", "connected": True, "neckAngle": 10.0, "trunkAngle": 6.0, "shoulderAngle": 5.0, "kneeAngle": 98.0, "issues": [], "recommendation": "Maintain current posture. Stand and stretch every 30min."},
    {"id": "A3", "name": "Workstation A3", "worker": "\u2014", "task": "Idle", "risk": "low", "healthScore": 100, "camera": "\u2014", "connected": False, "neckAngle": 0.0, "trunkAngle": 0.0, "shoulderAngle": 0.0, "kneeAngle": 0.0, "issues": [], "recommendation": "Station available."},
    {"id": "B1", "name": "Workstation B1", "worker": "Chen Wei", "task": "CNC Operation", "risk": "moderate", "healthScore": 68, "camera": "CAM-002", "connected": True, "neckAngle": 26.0, "trunkAngle": 10.0, "shoulderAngle": 20.0, "kneeAngle": 172.0, "issues": ["Sustained neck flexion", "Shoulder elevation during measurement"], "recommendation": "Raise control panel angle. Use anti-fatigue mat."},
    {"id": "B2", "name": "Workstation B2", "worker": "Priya Sharma", "task": "PCB Inspection", "risk": "moderate", "healthScore": 74, "camera": "CAM-004", "connected": True, "neckAngle": 16.0, "trunkAngle": 24.0, "shoulderAngle": 8.0, "kneeAngle": 168.0, "issues": ["Prolonged trunk flexion", "Forward lean during inspection"], "recommendation": "Use adjustable PCB holder. Bring work to eye level."},
    {"id": "B3", "name": "Workstation B3", "worker": "\u2014", "task": "Maintenance", "risk": "low", "healthScore": 100, "camera": "\u2014", "connected": False, "neckAngle": 0.0, "trunkAngle": 0.0, "shoulderAngle": 0.0, "kneeAngle": 0.0, "issues": [], "recommendation": "Station under maintenance."},
    {"id": "C1", "name": "Workstation C1", "worker": "James Kowalski", "task": "Pallet Stacking", "risk": "high", "healthScore": 42, "camera": "CAM-003", "connected": True, "neckAngle": 14.0, "trunkAngle": 36.0, "shoulderAngle": 16.0, "kneeAngle": 66.0, "issues": ["Deep trunk flexion during lift", "Knee angle below threshold", "Asymmetrical load distribution"], "recommendation": "Use pallet jack for loads >20kg. Enforce proper squat technique."},
    {"id": "C2", "name": "Workstation C2", "worker": "Sarah Jenkins", "task": "Welding", "risk": "high", "healthScore": 38, "camera": "CAM-005", "connected": True, "neckAngle": 30.0, "trunkAngle": 28.0, "shoulderAngle": 32.0, "kneeAngle": 88.0, "issues": ["Neck flexion >30\u00b0", "Shoulder elevation spike", "Trunk rotation during weld"], "recommendation": "Adjust welding mask counterweight. Rotate to different task every 90min."},
    {"id": "C3", "name": "Workstation C3", "worker": "Maria Santos", "task": "Packaging", "risk": "moderate", "healthScore": 62, "camera": "CAM-006", "connected": True, "neckAngle": 18.0, "trunkAngle": 20.0, "shoulderAngle": 12.0, "kneeAngle": 102.0, "issues": ["Repetitive shoulder motion", "Minor wrist deviation"], "recommendation": "Vary packaging motions. Use ergonomic box cutter."},
    {"id": "D1", "name": "Workstation D1", "worker": "David Park", "task": "Assembly", "risk": "moderate", "healthScore": 58, "camera": "CAM-002", "connected": True, "neckAngle": 24.0, "trunkAngle": 16.0, "shoulderAngle": 18.0, "kneeAngle": 148.0, "issues": ["Neck strain from looking down", "Shoulder asymmetry"], "recommendation": "Adjust chair height. Use document holder at eye level."},
    {"id": "D2", "name": "Workstation D2", "worker": "Lisa Chen", "task": "Welding", "risk": "high", "healthScore": 35, "camera": "CAM-005", "connected": True, "neckAngle": 28.0, "trunkAngle": 32.0, "shoulderAngle": 36.0, "kneeAngle": 84.0, "issues": ["Deep trunk flexion", "Critical shoulder elevation", "Knee angle below safe range"], "recommendation": "Immediate ergonomic assessment required. Rotate to light duty."},
    {"id": "D3", "name": "Workstation D3", "worker": "Ahmed Hassan", "task": "Inspection", "risk": "low", "healthScore": 90, "camera": "CAM-004", "connected": True, "neckAngle": 8.0, "trunkAngle": 10.0, "shoulderAngle": 6.0, "kneeAngle": 165.0, "issues": [], "recommendation": "All metrics nominal. Continue current practice."},
]

# ---------------------------------------------------------------------------
# Deployment metrics
# ---------------------------------------------------------------------------

DEPLOYMENT = {
    "camerasOnline": 5,
    "totalCameras": 6,
    "workstationsActive": 10,
    "totalWorkstations": 12,
    "activeWorkers": 10,
    "highRiskCount": 3,
    "averageHealthScore": 68.9,
    "edgeCpuPercent": 62.0,
    "edgeGpuPercent": 78.0,
    "edgeRamPercent": 54.0,
    "edgeTemperature": 68.0,
    "edgeUptime": "14d 6h 22m",
    "inferenceMs": 24,
    "inferenceFps": 30,
    "modelVersion": "ergo-mlp-v3.2",
    "cameraLatencyMs": "18ms",
    "storageUsedGb": 342,
    "storageTotalGb": 1000,
    "backendVersion": "v2.4.1",
    "aiModelStatus": "online",
    "edgeDeviceStatus": "online",
    "databaseStatus": "online",
    "websocketStatus": "online",
    "lastSyncAgo": "2s ago",
}

# ---------------------------------------------------------------------------
# Manager summary
# ---------------------------------------------------------------------------

MANAGER = {
    "registeredWorkers": 10,
    "highRiskWorkers": 3,
    "todayAlerts": 8,
    "sessionsCompleted": 42,
    "mostCommonIssue": "Neck Flexion",
    "workers": [
        {"id": "WA-4092", "name": "Marcus Thorne", "status": "moderate", "task": "Assembly Line B", "risk": 42.0},
        {"id": "WA-2104", "name": "Elena Rodriguez", "status": "low", "task": "Loading Dock", "risk": 18.0},
        {"id": "WA-3381", "name": "Chen Wei", "status": "low", "task": "Quality Control", "risk": 12.0},
        {"id": "WA-5562", "name": "Sarah Jenkins", "status": "high", "task": "Fabrication", "risk": 68.0},
        {"id": "WA-1099", "name": "James Kowalski", "status": "low", "task": "Assembly Line A", "risk": 22.0},
        {"id": "WA-6712", "name": "Priya Sharma", "status": "moderate", "task": "Packaging", "risk": 38.0},
        {"id": "WA-4431", "name": "Ahmed Hassan", "status": "low", "task": "Inspection", "risk": 15.0},
        {"id": "WA-8876", "name": "Lisa Chen", "status": "high", "task": "Welding", "risk": 72.0},
        {"id": "WA-3321", "name": "David Park", "status": "moderate", "task": "Assembly Line A", "risk": 45.0},
        {"id": "WA-7789", "name": "Maria Santos", "status": "low", "task": "Packing", "risk": 20.0},
    ],
    "departmentHeatmap": [
        {"department": "Assembly", "averageRisk": 36.3, "workerCount": 3, "highRiskCount": 0, "level": "moderate"},
        {"department": "Fabrication", "averageRisk": 70.0, "workerCount": 1, "highRiskCount": 1, "level": "high"},
        {"department": "Inspection", "averageRisk": 15.0, "workerCount": 1, "highRiskCount": 0, "level": "low"},
        {"department": "Packaging", "averageRisk": 29.0, "workerCount": 2, "highRiskCount": 0, "level": "moderate"},
        {"department": "Quality Control", "averageRisk": 12.0, "workerCount": 1, "highRiskCount": 0, "level": "low"},
        {"department": "Welding", "averageRisk": 72.0, "workerCount": 1, "highRiskCount": 1, "level": "high"},
        {"department": "Loading Dock", "averageRisk": 18.0, "workerCount": 1, "highRiskCount": 0, "level": "low"},
    ],
}

# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

ALERTS = [
    {"id": "A-001", "severity": "critical", "title": "Neck Flexion >30\u00b0 \u2014 Marcus Thorne", "description": "Sustained neck flexion at 34\u00b0 for 12s in Zone C.", "timestamp": "2026-06-30T14:30:00Z", "worker": "Marcus Thorne", "read": False},
    {"id": "A-002", "severity": "critical", "title": "Critical Biomechanical Load \u2014 James Kowalski", "description": "Trunk 38\u00b0 + Knee 62\u00b0 during pallet lift.", "timestamp": "2026-06-30T14:28:00Z", "worker": "James Kowalski", "read": False},
    {"id": "A-003", "severity": "warning", "title": "Recommendation Issued", "description": "Lower component tray at Workstation B-12.", "timestamp": "2026-06-30T14:25:00Z", "worker": "Marcus Thorne", "read": False},
    {"id": "A-004", "severity": "resolved", "title": "Posture Corrected \u2014 Elena Rodriguez", "description": "Neck flexion reduced from 22\u00b0 to 12\u00b0.", "timestamp": "2026-06-30T14:22:00Z", "worker": "Elena Rodriguez", "read": True},
    {"id": "A-005", "severity": "info", "title": "Safety Report Generated", "description": "Monthly safety report ready for review.", "timestamp": "2026-06-30T14:20:00Z", "worker": None, "read": False},
    {"id": "A-006", "severity": "warning", "title": "Camera CAM-004 Offline", "description": "QC camera disconnected for 45s.", "timestamp": "2026-06-30T14:15:00Z", "worker": None, "read": True},
    {"id": "A-007", "severity": "warning", "title": "Break Recommended \u2014 Chen Wei", "description": "Micro-break recommended. Sustained neck flexion for 2+ hours.", "timestamp": "2026-06-30T14:05:00Z", "worker": "Chen Wei", "read": False},
    {"id": "A-008", "severity": "critical", "title": "Shoulder Elevation 36\u00b0 \u2014 Lisa Chen", "description": "Right shoulder at 36\u00b0 during welding.", "timestamp": "2026-06-30T13:55:00Z", "worker": "Lisa Chen", "read": False},
]
