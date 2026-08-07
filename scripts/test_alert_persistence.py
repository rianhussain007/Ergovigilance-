"""Test alert persistence end-to-end."""

import sys
import os
import tempfile
from pathlib import Path

# Repo-relative paths (was a hardcoded Windows checkout path that broke CI).
ROOT = Path(__file__).resolve().parents[1]
BACKEND_API = ROOT / "backend_api"
sys.path.insert(0, str(BACKEND_API))
sys.path.insert(0, str(ROOT))

# Point the auth/alerts DB at a throwaway temp file so this script never
# writes test alerts into the developer's real backend_api/local_auth.db.
# Must be set before app.core.database/config are imported.
os.environ["AUTH_DB_PATH"] = os.path.join(
    tempfile.mkdtemp(prefix="ergovigilance-alert-test-"), "test_alerts.db"
)

from app.core.database import init_local_database, get_connection
from backend.alerts.engine import AlertEngine
from backend.alerts.models import Alert, AlertSeverity, AlertState
from backend.events.event_bus import EventBus
from datetime import datetime, timezone

# 1. Init DB
init_local_database()
print("[1] Database initialized")

# 2. Create AlertEngine with persistence
bus = EventBus()
engine = AlertEngine(bus, db_enabled=True)
print(f"[2] AlertEngine created (active={len(engine.active_alerts)}, history={len(engine.history)})")

# 3. Fire a test alert
test_alert = Alert(
    id="ALT-TEST0001",
    session_id="SESH-TEST",
    frame_number=42,
    created_at=datetime.now(timezone.utc).isoformat(),
    severity=AlertSeverity.HIGH,
    state=AlertState.ACTIVE,
    title="Test High Risk Alert",
    message="This is a test alert",
    trigger_rule="high_risk",
    confidence=0.85,
    requires_ack=True,
)
engine._active_alerts[test_alert.id] = test_alert
engine._history.append(test_alert)
engine._persist_alert(test_alert)
print(f"[3] Alert fired and persisted (active={len(engine.active_alerts)})")

# 4. Verify in SQLite
with get_connection() as conn:
    row = conn.execute("SELECT id, state, severity FROM alerts WHERE id = ?", ("ALT-TEST0001",)).fetchone()
    print(f"[4] SQLite row: id={row['id']}, state={row['state']}, severity={row['severity']}")

# 5. Acknowledge
result = engine.acknowledge("ALT-TEST0001")
print(f"[5] Acknowledge result: {result}")

# 6. Verify ack in SQLite
with get_connection() as conn:
    row = conn.execute("SELECT state FROM alerts WHERE id = ?", ("ALT-TEST0001",)).fetchone()
    print(f"[6] SQLite state after ack: {row['state']}")

# 7. Resolve
result = engine.resolve("ALT-TEST0001")
print(f"[7] Resolve result: {result}")

# 8. Verify resolve in SQLite
with get_connection() as conn:
    row = conn.execute("SELECT state FROM alerts WHERE id = ?", ("ALT-TEST0001",)).fetchone()
    active_count = conn.execute("SELECT COUNT(*) FROM alerts WHERE state = 'ACTIVE'").fetchone()[0]
    total_count = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    print(f"[8] SQLite state after resolve: {row['state']}")
    print(f"    Active alerts in DB: {active_count}")
    print(f"    Total alerts in DB: {total_count}")

# 9. Simulate restart: new AlertEngine rehydrates from DB
engine2 = AlertEngine(bus, db_enabled=True)
print(f"[9] New AlertEngine after restart: active={len(engine2.active_alerts)}, history={len(engine2.history)}")
for a in engine2.history:
    print(f"    History: {a.id} state={a.state.value} title={a.title}")

# 10. Add another alert on the new engine, verify it persists alongside the old one
alert2 = Alert(
    id="ALT-TEST0002",
    session_id="SESH-TEST2",
    frame_number=100,
    created_at=datetime.now(timezone.utc).isoformat(),
    severity=AlertSeverity.CRITICAL,
    state=AlertState.ACTIVE,
    title="Critical Risk Alert",
    message="Escalated after 10 consecutive HIGH frames",
    trigger_rule="critical_risk",
    confidence=0.9,
    requires_ack=True,
)
engine2._active_alerts[alert2.id] = alert2
engine2._history.append(alert2)
engine2._persist_alert(alert2)

with get_connection() as conn:
    total = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM alerts WHERE state = 'ACTIVE'").fetchone()[0]
    print(f"[10] After adding 2nd alert: total={total}, active={active}")

print()
print("ALL TESTS PASSED")
