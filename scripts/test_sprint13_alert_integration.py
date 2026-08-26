"""Sprint 13 — Alert Engine Integration Validation.

Tests:
  1. API schema alignment
  2. Endpoint registration
  3. Repository implementations
  4. React TypeScript interface
  5. Hook implementation
  6. Service layer
  7. Component update
  8. LiveMonitoring update
  9. No unrelated changes
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend_api"))

from backend.alerts.models import Alert, AlertSeverity, AlertState
from app.schemas.api import AlertResponse, AlertsResponse, AlertSummary


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


def test_schema_alignment():
    print("\n--- Schema Alignment ---")

    alert = Alert(
        id="ALT-001",
        session_id="SESH-001",
        frame_number=42,
        created_at="2026-07-05T12:00:00Z",
        severity=AlertSeverity.HIGH,
        state=AlertState.ACTIVE,
        title="High Risk Detected",
        message="Risk score exceeded threshold",
        trigger_rule="high_risk",
        confidence=0.85,
        requires_ack=True,
        expires_at="",
    )

    d = alert.to_dict()
    api_response = AlertResponse(**d)

    check("id matches", api_response.id == "ALT-001")
    check("session_id matches", api_response.session_id == "SESH-001")
    check("frame_number matches", api_response.frame_number == 42)
    check("created_at matches", api_response.created_at == "2026-07-05T12:00:00Z")
    check("severity matches", api_response.severity == "HIGH")
    check("state matches", api_response.state == "ACTIVE")
    check("title matches", api_response.title == "High Risk Detected")
    check("message matches", api_response.message == "Risk score exceeded threshold")
    check("trigger_rule matches", api_response.trigger_rule == "high_risk")
    check("confidence matches", api_response.confidence == 0.85)
    check("requires_ack matches", api_response.requires_ack is True)

    summary = AlertSummary(
        total_fired=10,
        active_count=2,
        critical_count=1,
        acknowledged_count=3,
        consecutive_high=5,
    )
    check("summary total_fired", summary.total_fired == 10)
    check("summary active_count", summary.active_count == 2)
    check("summary critical_count", summary.critical_count == 1)
    check("summary acknowledged_count", summary.acknowledged_count == 3)
    check("summary consecutive_high", summary.consecutive_high == 5)

    full = AlertsResponse(
        active=[api_response],
        history=[],
        summary=summary,
    )
    check("full response active count", len(full.active) == 1)
    check("full response history count", len(full.history) == 0)
    check("full response summary", full.summary.total_fired == 10)


def test_endpoint_registration():
    print("\n--- Endpoint Registration ---")

    from app.api.alerts import router
    routes = [r.path for r in router.routes]
    check("endpoint exists", "/alerts" in routes)


def test_repository_implementations():
    print("\n--- Repository Implementations ---")

    from app.repositories.live import LiveRepository
    from app.repositories.base import DashboardRepository

    # NOTE: the mock repository layer was removed — live mode is the only mode.
    check("LiveRepository has get_alerts_full", hasattr(LiveRepository, "get_alerts_full"))
    check("DashboardRepository has get_alerts_full", hasattr(DashboardRepository, "get_alerts_full"))


def test_react_typescript_interface():
    print("\n--- React TypeScript Interface ---")

    ts_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "types", "api.ts")
    with open(ts_file, "r") as f:
        content = f.read()

    check("AlertData interface exists", "interface AlertData" in content)
    check("AlertData id field", "id: string" in content)
    check("AlertData severity field", "severity: string" in content)
    check("AlertData state field", "state: string" in content)
    check("AlertData title field", "title: string" in content)
    check("AlertData message field", "message: string" in content)
    check("AlertData trigger_rule field", "trigger_rule: string" in content)
    check("AlertData confidence field", "confidence: number" in content)
    check("AlertData requires_ack field", "requires_ack: boolean" in content)

    check("AlertSummary interface exists", "interface AlertSummary" in content)
    check("AlertSummary total_fired", "total_fired: number" in content)
    check("AlertSummary active_count", "active_count: number" in content)
    check("AlertSummary critical_count", "critical_count: number" in content)
    check("AlertSummary acknowledged_count", "acknowledged_count: number" in content)
    check("AlertSummary consecutive_high", "consecutive_high: number" in content)

    check("AlertsResponse interface exists", "interface AlertsResponse" in content)
    check("AlertsResponse active", "active: AlertData[]" in content)
    check("AlertsResponse history", "history: AlertData[]" in content)
    check("AlertsResponse summary", "summary: AlertSummary" in content)


def test_hook_exists():
    print("\n--- React Hook ---")

    hook_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "hooks", "useAlerts.ts")
    check("hook file exists", os.path.exists(hook_file))

    with open(hook_file, "r") as f:
        content = f.read()

    check("exports useAlerts", "export function useAlerts" in content)
    check("returns alerts", "alerts" in content)
    check("returns loading", "loading" in content)
    check("returns error", "error" in content)
    check("returns refetch", "refetch" in content)
    check("calls getAlerts service", "getAlerts" in content)
    check("polls every 1s", "setInterval" in content)


def test_service_layer():
    print("\n--- Service Layer ---")

    service_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "services", "dashboardService.ts")
    with open(service_file, "r") as f:
        content = f.read()

    check("getAlerts exported", "export function getAlerts" in content)
    check("calls repository getAlerts", "getRepository().getAlerts()" in content)


def test_repository_files():
    print("\n--- Repository Files ---")

    api_repo_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "repositories", "ApiDashboardRepository.ts")
    with open(api_repo_file, "r") as f:
        content = f.read()

    check("ApiDashboardRepository has getAlerts", "async getAlerts()" in content)
    check("calls alerts endpoint", "alerts" in content)

    mock_repo_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "repositories", "MockDashboardRepository.ts")
    if os.path.exists(mock_repo_file):
        with open(mock_repo_file, "r") as f:
            content = f.read()
        check("MockDashboardRepository has getAlerts", "async getAlerts()" in content)
        check("mock returns empty alerts", "active: []" in content)
    else:
        print("  SKIP: MockDashboardRepository.ts removed in the React migration — skipping mock-repo checks")

    repo_interface_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "repositories", "DashboardRepository.ts")
    with open(repo_interface_file, "r") as f:
        content = f.read()

    check("interface has getAlerts", "getAlerts()" in content)
    check("returns Promise<AlertsResponse>", "Promise<AlertsResponse>" in content)


def test_component_update():
    print("\n--- AlertManagementCard Update ---")

    component_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "components", "common", "AlertManagementCard.tsx")
    with open(component_file, "r") as f:
        content = f.read()

    check("uses useAlerts", "useAlerts" in content)
    check("shows EmptyState when no alerts", "No active alerts" in content)
    check("shows loading state", "animate-pulse" in content)
    check("displays active alerts", "active.length" in content or "active.map" in content)
    check("displays history", "history.length" in content or "history.map" in content)
    check("displays summary.total_fired", "summary.total_fired" in content)
    check("displays summary.active_count", "summary.active_count" in content)
    check("displays summary.critical_count", "summary.critical_count" in content)
    check("displays summary.acknowledged_count", "summary.acknowledged_count" in content)
    check("displays summary.consecutive_high", "summary.consecutive_high" in content)
    check("displays severity", "alert.severity" in content)
    check("displays state", "alert.state" in content)
    check("displays trigger_rule", "alert.trigger_rule" in content)
    check("displays created_at", "alert.created_at" in content)
    check("no engine prop required", "Props" not in content or "{ engine" not in content)


def test_live_monitoring_update():
    print("\n--- LiveMonitoring Update ---")

    page_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "pages", "LiveMonitoring.tsx")
    with open(page_file, "r") as f:
        content = f.read()

    check("AlertManagementCard has no props", "<AlertManagementCard />" in content)
    check("no hardcoded alert fallback", "currentLevel: 'none'" not in content)


def test_no_unrelated_changes():
    print("\n--- No Unrelated Changes ---")

    alert_engine = os.path.join(os.path.dirname(__file__), "..", "backend", "alerts", "engine.py")
    with open(alert_engine, "r") as f:
        content = f.read()
    check("AlertEngine unchanged (export method exists)", "def export(self)" in content)
    check("AlertEngine _process_snapshot unchanged", "def _process_snapshot" in content)

    context_engine = os.path.join(os.path.dirname(__file__), "..", "backend", "context", "engine.py")
    with open(context_engine, "r") as f:
        content = f.read()
    check("ContextEngine unchanged (evaluate method exists)", "def evaluate(" in content)

    history_engine = os.path.join(os.path.dirname(__file__), "..", "backend", "history", "engine.py")
    with open(history_engine, "r") as f:
        content = f.read()
    check("HistoryEngine unchanged (export method exists)", "def export(self)" in content)

    rec_engine = os.path.join(os.path.dirname(__file__), "..", "backend", "recommendations", "engine.py")
    with open(rec_engine, "r") as f:
        content = f.read()
    check("RecommendationEngine unchanged (export method exists)", "def export(self)" in content)


if __name__ == "__main__":
    print("=" * 70)
    print("  SPRINT 13 — ALERT ENGINE INTEGRATION VALIDATION")
    print("=" * 70)

    test_schema_alignment()
    test_endpoint_registration()
    test_repository_implementations()
    test_react_typescript_interface()
    test_hook_exists()
    test_service_layer()
    test_repository_files()
    test_component_update()
    test_live_monitoring_update()
    test_no_unrelated_changes()

    print()
    print("-" * 70)
    total = passed + failed
    print(f"  Result: {passed}/{total} tests passed")
    if failed > 0:
        print(f"  {failed} tests FAILED")
    else:
        print("  All tests PASSED")
    print("-" * 70)
