"""Sprint 15 — Risk History Engine Integration Validation.

Tests:
  1. API schema alignment
  2. Endpoint registration
  3. Repository implementations
  4. React TypeScript interface
  5. Hook implementation
  6. Service layer
  7. Component update
  8. LiveMonitoring update
  9. No regressions
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend_api"))

from backend.history.models import HistoryStats, RiskDistribution
from app.schemas.api import HistoryPoint, HistoryStatistics, HistoryResponse


passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        msg = f"  FAIL: {name}"
        if detail:
            msg += f" ({detail})"
        print(msg)


# ── Section 1: Schema Alignment ───────────────────────────────────────

def test_schema_alignment():
    print("\n--- Schema Alignment ---")

    point = HistoryPoint(
        time="12:34:56",
        value=42.5,
        fatigue=18.3,
        exposure=11.0,
        risk_level="MEDIUM",
    )

    check("point time", point.time == "12:34:56")
    check("point value", point.value == 42.5)
    check("point fatigue", point.fatigue == 18.3)
    check("point exposure", point.exposure == 11.0)
    check("point risk_level", point.risk_level == "MEDIUM")

    stats = HistoryStatistics(
        frames_stored=120,
        session_duration_seconds=36.5,
        average_risk=37.2,
        maximum_risk=81.0,
        minimum_risk=5.0,
        average_fatigue=24.1,
        average_exposure=19.5,
    )

    check("stats frames_stored", stats.frames_stored == 120)
    check("stats session_duration_seconds", stats.session_duration_seconds == 36.5)
    check("stats average_risk", stats.average_risk == 37.2)
    check("stats maximum_risk", stats.maximum_risk == 81.0)
    check("stats minimum_risk", stats.minimum_risk == 5.0)
    check("stats average_fatigue", stats.average_fatigue == 24.1)
    check("stats average_exposure", stats.average_exposure == 19.5)

    full = HistoryResponse(points=[point], statistics=stats)
    check("full response has points", len(full.points) == 1)
    check("full response has statistics", full.statistics.frames_stored == 120)

    empty = HistoryResponse(points=[], statistics=HistoryStatistics())
    check("empty response has no points", len(empty.points) == 0)
    check("empty response zero stats", empty.statistics.frames_stored == 0)


# ── Section 2: Endpoint Registration ──────────────────────────────────

def test_endpoint_registration():
    print("\n--- Endpoint Registration ---")

    from app.api.history import router
    routes = [r.path for r in router.routes]
    check("endpoint exists", "/history" in routes)


# ── Section 3: Repository Implementations ─────────────────────────────

def test_repository_implementations():
    print("\n--- Repository Implementations ---")

    from app.repositories.live import LiveRepository
    from app.repositories.base import DashboardRepository

    # NOTE: the mock repository layer was removed — live mode is the only mode.
    check("LiveRepository has get_history", hasattr(LiveRepository, "get_history"))
    check("DashboardRepository has get_history", hasattr(DashboardRepository, "get_history"))


# ── Section 4: React TypeScript Interface ─────────────────────────────

def test_react_typescript_interface():
    print("\n--- React TypeScript Interface ---")

    ts_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "types", "api.ts")
    with open(ts_file, "r") as f:
        content = f.read()

    check("HistoryPoint interface exists", "interface HistoryPoint" in content)
    check("HistoryPoint time field", "time: string" in content)
    check("HistoryPoint value field", "value: number" in content)
    check("HistoryPoint fatigue field", "fatigue: number" in content)
    check("HistoryPoint exposure field", "exposure: number" in content)
    check("HistoryPoint risk_level field", "risk_level: string" in content)

    check("HistoryStatistics interface exists", "interface HistoryStatistics" in content)
    check("HistoryStatistics frames_stored field", "frames_stored: number" in content)
    check("HistoryStatistics average_risk field", "average_risk: number" in content)
    check("HistoryStatistics maximum_risk field", "maximum_risk: number" in content)
    check("HistoryStatistics minimum_risk field", "minimum_risk: number" in content)
    check("HistoryStatistics average_fatigue field", "average_fatigue: number" in content)
    check("HistoryStatistics average_exposure field", "average_exposure: number" in content)

    check("HistoryResponse interface exists", "interface HistoryResponse" in content)
    check("HistoryResponse points field", "points: HistoryPoint[]" in content)
    check("HistoryResponse statistics field", "statistics: HistoryStatistics" in content)


# ── Section 5: Hook Implementation ────────────────────────────────────

def test_hook_implementation():
    print("\n--- Hook Implementation ---")

    hook_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "hooks", "useHistory.ts")
    with open(hook_file, "r") as f:
        content = f.read()

    check("useHistory hook exists", "export function useHistory()" in content)
    check("imports useState", "useState" in content)
    check("imports useEffect", "useEffect" in content)
    check("imports useCallback", "useCallback" in content)
    check("imports useRef", "useRef" in content)
    check("calls getHistory", "getHistory" in content)
    check("polling interval set", "2000" in content)
    check("returns data", "data" in content)
    check("returns loading", "loading" in content)
    check("returns error", "error" in content)
    check("returns refetch", "refetch" in content)
    check("mountedRef pattern", "mountedRef" in content)
    check("silent background poll (setLoading(true) only on initial)", content.count("setLoading(true)") == 1)


# ── Section 6: Service Layer ──────────────────────────────────────────

def test_service_layer():
    print("\n--- Service Layer ---")

    svc_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "services", "dashboardService.ts")
    with open(svc_file, "r") as f:
        content = f.read()

    check("getHistory function exists", "export function getHistory()" in content)
    check("returns HistoryResponse", "HistoryResponse" in content)
    check("delegates to repository", "getRepository().getHistory()" in content)


# ── Section 7: Repository Interface ───────────────────────────────────

def test_repository_interface():
    print("\n--- Repository Interface ---")

    repo_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "repositories", "DashboardRepository.ts")
    with open(repo_file, "r") as f:
        content = f.read()

    check("getHistory in interface", "getHistory(): Promise<HistoryResponse>" in content)

    api_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "repositories", "ApiDashboardRepository.ts")
    with open(api_file, "r") as f:
        content = f.read()

    check("getHistory in ApiDashboardRepository", "async getHistory()" in content)
    check("fetches history endpoint", "history" in content and "API_BASE" in content)

    mock_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "repositories", "MockDashboardRepository.ts")
    if os.path.exists(mock_file):
        with open(mock_file, "r") as f:
            content = f.read()
        check("getHistory in MockDashboardRepository", "async getHistory()" in content)
        check("returns empty points for mock", "points: []" in content)
    else:
        print("  SKIP: MockDashboardRepository.ts removed in the React migration — skipping mock-repo checks")


# ── Section 8: LiveMonitoring Update ──────────────────────────────────

def test_livemonitoring_update():
    print("\n--- LiveMonitoring Update ---")

    lm_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "pages", "LiveMonitoring.tsx")
    with open(lm_file, "r") as f:
        content = f.read()

    check("imports useHistory", "useHistory" in content)
    check("calls useHistory hook", "useHistory()" in content)
    check("uses history.data.points for chart", "history.data.points" in content)
    check("empty state check uses history", "history.data.points.length === 0" in content)
    check("passes history points to chart", "data={history.data.points}" in content)


# ── Section 9: HistoryEngine Export ───────────────────────────────────

def test_history_engine_export():
    print("\n--- HistoryEngine Export ---")

    from backend.history.engine import HistoryEngine
    from backend.events.event_bus import EventBus

    bus = EventBus()
    engine = HistoryEngine(bus)

    export = engine.export()
    check("export has snapshots", "snapshots" in export)
    check("export has statistics", "statistics" in export)
    check("export has total_received", "total_received" in export)
    check("export has total_pruned", "total_pruned" in export)
    check("snapshots is list", isinstance(export["snapshots"], list))
    check("statistics is dict", isinstance(export["statistics"], dict))


# ── Section 10: Chart Compatibility ───────────────────────────────────

def test_chart_compatibility():
    print("\n--- Chart Compatibility ---")

    ts_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "types", "api.ts")
    with open(ts_file, "r") as f:
        content = f.read()

    check("RiskDataPoint still exists", "interface RiskDataPoint" in content)
    check("RiskDataPoint has time", "time: string" in content)
    check("RiskDataPoint has value", "value: number" in content)

    check("HistoryPoint has time", "time: string" in content)
    check("HistoryPoint has value", "value: number" in content)

    chart_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "components", "charts", "RiskHistoryChart.tsx")
    with open(chart_file, "r") as f:
        content = f.read()

    check("chart uses RiskDataPoint", "RiskDataPoint" in content)
    check("chart renders AreaChart", "AreaChart" in content)
    check("chart has no mock fallback", "mock" not in content.lower())


# ── Run ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Sprint 15 — Risk History Engine Integration Validation")
    print("=" * 60)

    test_schema_alignment()
    test_endpoint_registration()
    test_repository_implementations()
    test_react_typescript_interface()
    test_hook_implementation()
    test_service_layer()
    test_repository_interface()
    test_livemonitoring_update()
    test_history_engine_export()
    test_chart_compatibility()

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
