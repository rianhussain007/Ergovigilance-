"""Session Persistence Layer — comprehensive test suite.

Tests:
  1. SessionRecord serialization (to_dict/from_dict roundtrip)
  2. JsonSessionRepository CRUD (save/load/list/delete)
  3. Corrupted file handling
  4. Large session handling
  5. PersistenceService lifecycle (start/end/save)
  6. Engine export() methods
  7. Performance (save/load under limits)
  8. Migration path (SQL-ready design)
"""

import json
import os
import sys
import time
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.getcwd())

from backend.persistence.models import SessionRecord
from backend.persistence.json_repository import JsonSessionRepository
from backend.persistence.service import PersistenceService
from backend.events.event_bus import EventBus
from backend.history.engine import HistoryEngine
from backend.alerts.engine import AlertEngine
from backend.recommendations.engine import RecommendationEngine
from backend.context.engine import ContextIntelligenceEngine
from backend.context.engine import ContextSnapshot


def make_snapshot(
    risk: float = 0.0,
    fatigue: float = 0.0,
    exposure: float = 0.0,
    session_id: str = "test-session",
    frame: int = 1,
) -> ContextSnapshot:
    """Create a test ContextSnapshot."""
    return ContextSnapshot(
        session_id=session_id,
        frame_number=frame,
        captured_at="2026-07-05T12:00:00Z",
        worker_id="worker-01",
        neck_flexion=risk,
        trunk_flexion=risk,
        shoulder_symmetry=risk,
        alignment_deviation=risk,
        knee_angle=risk,
        fatigue_score=fatigue,
        exposure_score=exposure,
        final_risk=risk,
        risk_level="HIGH" if risk >= 70 else "MEDIUM" if risk >= 40 else "LOW",
        safety_state="CRITICAL" if risk >= 70 else "RECOVERY" if risk >= 40 else "SAFE",
        feature_scores={"neck_flexion": risk},
        active_rules=("rule1",) if risk >= 70 else (),
        explanation=f"Risk: {risk}",
    )


def make_record(session_id: str = "test-session") -> SessionRecord:
    """Create a test SessionRecord."""
    return SessionRecord(
        session_id=session_id,
        started_at="2026-07-05T12:00:00Z",
        ended_at="2026-07-05T12:30:00Z",
        worker_id="worker-01",
        statistics={"risk": {"average": 45.2}},
        snapshots=[{"frame": 1, "risk": 50.0}],
        alerts=[{"id": "ALT-001", "severity": "HIGH"}],
        recommendations=[{"id": "REC-001", "title": "Take a break"}],
    )


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


def test_session_record():
    print("\n--- SessionRecord ---")

    r = make_record()
    check("session_id", r.session_id == "test-session")
    check("started_at", r.started_at == "2026-07-05T12:00:00Z")
    check("worker_id", r.worker_id == "worker-01")
    check("snapshots count", len(r.snapshots) == 1)
    check("alerts count", len(r.alerts) == 1)
    check("recommendations count", len(r.recommendations) == 1)

    d = r.to_dict()
    check("to_dict keys", set(d.keys()) == {
        "session_id", "started_at", "ended_at", "worker_id",
        "statistics", "snapshots", "alerts", "recommendations"
    })

    r2 = SessionRecord.from_dict(d)
    check("from_dict roundtrip", r2.session_id == r.session_id)
    check("from_dict statistics", r2.statistics == r.statistics)
    check("from_dict snapshots", r2.snapshots == r.snapshots)

    r3 = SessionRecord.from_dict({})
    check("from_dict defaults", r3.session_id == "")
    check("from_dict defaults snapshots", r3.snapshots == [])


def test_json_repository_crud():
    print("\n--- JsonRepository CRUD ---")

    tmpdir = tempfile.mkdtemp()
    try:
        repo = JsonSessionRepository(tmpdir)

        check("list empty", repo.list_sessions() == [])

        r = make_record("session-001")
        repo.save(r)

        check("list after save", repo.list_sessions() == ["session-001"])
        check("exists", repo.exists("session-001"))
        check("not exists", not repo.exists("session-999"))

        loaded = repo.load("session-001")
        check("load found", loaded is not None)
        check("load session_id", loaded.session_id == "session-001")
        check("load worker_id", loaded.worker_id == "worker-01")
        check("load snapshots", len(loaded.snapshots) == 1)

        check("load not found", repo.load("session-999") is None)

        r2 = make_record("session-002")
        repo.save(r2)
        check("list two", sorted(repo.list_sessions()) == ["session-001", "session-002"])

        check("delete", repo.delete("session-001"))
        check("delete not found", not repo.delete("session-999"))
        check("list after delete", repo.list_sessions() == ["session-002"])

    finally:
        shutil.rmtree(tmpdir)


def test_corrupted_file():
    print("\n--- Corrupted File Handling ---")

    tmpdir = tempfile.mkdtemp()
    try:
        repo = JsonSessionRepository(tmpdir)

        # Write invalid JSON
        bad_path = os.path.join(tmpdir, "bad-session.json")
        with open(bad_path, "w") as f:
            f.write("{invalid json}}}")

        result = repo.load("bad-session")
        check("corrupted file returns None", result is None)

        # Write valid JSON but wrong structure
        wrong_path = os.path.join(tmpdir, "wrong-session.json")
        with open(wrong_path, "w") as f:
            json.dump({"foo": "bar"}, f)

        result = repo.load("wrong-session")
        check("wrong structure returns record with defaults", result is not None)
        check("wrong structure session_id empty", result.session_id == "")

    finally:
        shutil.rmtree(tmpdir)


def test_large_session():
    print("\n--- Large Session Handling ---")

    tmpdir = tempfile.mkdtemp()
    try:
        repo = JsonSessionRepository(tmpdir)

        snapshots = [{"frame": i, "risk": float(i % 100)} for i in range(10000)]
        alerts = [{"id": f"ALT-{i:04d}", "severity": "HIGH"} for i in range(500)]
        recs = [{"id": f"REC-{i:04d}", "title": f"Rec {i}"} for i in range(200)]

        r = SessionRecord(
            session_id="large-session",
            started_at="2026-07-05T12:00:00Z",
            ended_at="2026-07-05T18:00:00Z",
            worker_id="worker-01",
            statistics={"history": {"frames_stored": 10000}},
            snapshots=snapshots,
            alerts=alerts,
            recommendations=recs,
        )

        t0 = time.perf_counter()
        repo.save(r)
        save_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        loaded = repo.load("large-session")
        load_ms = (time.perf_counter() - t0) * 1000

        check("large save/load roundtrip", loaded.session_id == "large-session")
        check("large snapshots count", len(loaded.snapshots) == 10000)
        check("large alerts count", len(loaded.alerts) == 500)
        check("large recommendations count", len(loaded.recommendations) == 200)
        check(f"large save time ({save_ms:.1f}ms < 200ms)", save_ms < 200)
        check(f"large load time ({load_ms:.1f}ms < 200ms)", load_ms < 200)

    finally:
        shutil.rmtree(tmpdir)


def test_engine_export():
    print("\n--- Engine Export Methods ---")

    bus = EventBus()
    history = HistoryEngine(bus, max_length=100)
    alerts = AlertEngine(bus)
    rec_engine = RecommendationEngine(bus, alerts, history)
    ctx = ContextIntelligenceEngine()

    # Process some snapshots
    for i in range(5):
        snap = ctx.evaluate(
            features={"neck_flexion": 80.0},
            issues=[],
            task_name="Neutral Standing",
            task_confidence=90.0,
            session_duration_seconds=float(i + 1) * 0.033,
            camera_confidence=95.0,
            delta_seconds=0.033,
        )
        bus.publish(
            __import__("backend.events.events", fromlist=["ContextSnapshotCreatedEvent"]).ContextSnapshotCreatedEvent(
                snapshot=snap
            )
        )

    # History export
    h_export = history.export()
    check("history export has snapshots", "snapshots" in h_export)
    check("history export has statistics", "statistics" in h_export)
    check("history export snapshots count", len(h_export["snapshots"]) == 5)
    check("history export total_received", h_export["total_received"] == 5)

    # Alert export
    a_export = alerts.export()
    check("alert export has active_alerts", "active_alerts" in a_export)
    check("alert export has history", "history" in a_export)
    check("alert export total_fired", a_export["total_fired"] >= 0)

    # Recommendation export
    r_export = rec_engine.export()
    check("recommendation export has bundle", "bundle" in r_export)
    check("recommendation export has total_generated", "total_generated" in r_export)


def test_persistence_service():
    print("\n--- PersistenceService Lifecycle ---")

    tmpdir = tempfile.mkdtemp()
    try:
        repo = JsonSessionRepository(tmpdir)
        service = PersistenceService(repo)
        bus = EventBus()
        history = HistoryEngine(bus)
        alerts = AlertEngine(bus)
        rec_engine = RecommendationEngine(bus, alerts, history)

        service.attach_history(history)
        service.attach_alerts(alerts)
        service.attach_recommendations(rec_engine)

        check("not active initially", not service.is_active)
        check("session_id is None", service.session_id is None)

        service.start_session("svc-session-001", "worker-01")
        check("active after start", service.is_active)
        check("session_id set", service.session_id == "svc-session-001")

        # Process some data
        ctx = ContextIntelligenceEngine()
        for i in range(3):
            snap = ctx.evaluate(
                features={"neck_flexion": 75.0},
                issues=[],
                task_name="Neutral Standing",
                task_confidence=90.0,
                session_duration_seconds=float(i + 1) * 0.033,
                camera_confidence=95.0,
                delta_seconds=0.033,
            )
            bus.publish(
                __import__("backend.events.events", fromlist=["ContextSnapshotCreatedEvent"]).ContextSnapshotCreatedEvent(
                    snapshot=snap
                )
            )

        # Save snapshot (mid-session)
        mid_record = service.save_snapshot()
        check("save_snapshot returns record", mid_record is not None)
        check("save_snapshot has session_id", mid_record.session_id == "svc-session-001")
        check("save_snapshot has snapshots", len(mid_record.snapshots) > 0)

        # End session
        record = service.end_session()
        check("end_session returns record", record is not None)
        check("not active after end", not service.is_active)
        check("record has session_id", record.session_id == "svc-session-001")
        check("record has worker_id", record.worker_id == "worker-01")
        check("record has snapshots", len(record.snapshots) > 0)
        check("record has statistics", "history" in record.statistics)
        check("record has alerts key", "alerts" in record.statistics)

        # Verify persisted
        loaded = service.load("svc-session-001")
        check("loaded after end", loaded is not None)
        check("loaded session_id", loaded.session_id == "svc-session-001")

        # List sessions
        check("list sessions", "svc-session-001" in service.list_sessions())

        # Delete
        check("delete session", service.delete("svc-session-001"))
        check("list after delete", service.list_sessions() == [])

    finally:
        shutil.rmtree(tmpdir)


def test_service_auto_end():
    print("\n--- Service Auto-End on New Session ---")

    tmpdir = tempfile.mkdtemp()
    try:
        repo = JsonSessionRepository(tmpdir)
        service = PersistenceService(repo)

        service.start_session("session-1", "w1")
        check("session 1 active", service.session_id == "session-1")

        service.start_session("session-2", "w2")
        check("session 2 active", service.session_id == "session-2")
        check("session 1 persisted", "session-1" in service.list_sessions())

    finally:
        shutil.rmtree(tmpdir)


def test_service_no_session():
    print("\n--- Service Without Active Session ---")

    tmpdir = tempfile.mkdtemp()
    try:
        repo = JsonSessionRepository(tmpdir)
        service = PersistenceService(repo)

        check("end_session returns None", service.end_session() is None)
        check("save_snapshot returns None", service.save_snapshot() is None)

    finally:
        shutil.rmtree(tmpdir)


def test_json_file_structure():
    print("\n--- JSON File Structure ---")

    tmpdir = tempfile.mkdtemp()
    try:
        repo = JsonSessionRepository(tmpdir)

        r = make_record("struct-test")
        repo.save(r)

        path = os.path.join(tmpdir, "struct-test.json")
        with open(path, "r") as f:
            raw = json.load(f)

        check("raw has session_id", "session_id" in raw)
        check("raw has started_at", "started_at" in raw)
        check("raw has ended_at", "ended_at" in raw)
        check("raw has worker_id", "worker_id" in raw)
        check("raw has statistics", "statistics" in raw)
        check("raw has snapshots", "snapshots" in raw)
        check("raw has alerts", "alerts" in raw)
        check("raw has recommendations", "recommendations" in raw)

        # Verify indented (pretty-printed)
        with open(path, "r") as f:
            content = f.read()
        check("file is pretty-printed", "\n  " in content)

    finally:
        shutil.rmtree(tmpdir)


def test_performance():
    print("\n--- Performance ---")

    tmpdir = tempfile.mkdtemp()
    try:
        repo = JsonSessionRepository(tmpdir)

        # Save 50 sessions
        t0 = time.perf_counter()
        for i in range(50):
            r = SessionRecord(
                session_id=f"perf-{i:03d}",
                started_at="2026-07-05T12:00:00Z",
                ended_at="2026-07-05T12:00:00Z",
                worker_id="worker-01",
                statistics={"frame_count": 3000},
                snapshots=[{"frame": j} for j in range(100)],
            )
            repo.save(r)
        save_ms = (time.perf_counter() - t0) * 1000

        check(f"save 50 sessions ({save_ms:.1f}ms < 500ms)", save_ms < 500)

        # List 50 sessions
        t0 = time.perf_counter()
        sessions = repo.list_sessions()
        list_ms = (time.perf_counter() - t0) * 1000
        check(f"list 50 sessions ({list_ms:.1f}ms < 10ms)", list_ms < 10)
        check("list count", len(sessions) == 50)

        # Load 50 sessions
        t0 = time.perf_counter()
        for sid in sessions:
            repo.load(sid)
        load_ms = (time.perf_counter() - t0) * 1000
        check(f"load 50 sessions ({load_ms:.1f}ms < 500ms)", load_ms < 500)

    finally:
        shutil.rmtree(tmpdir)


def test_migration_path():
    print("\n--- Migration Path (SQL-Ready Design) ---")

    r = make_record("migration-test")

    # Verify SessionRecord fields are SQL-mappable
    check("session_id is string", isinstance(r.session_id, str))
    check("started_at is string (ISO)", "T" in r.started_at)
    check("ended_at is string (ISO)", "T" in r.ended_at)
    check("worker_id is string", isinstance(r.worker_id, str))
    check("statistics is dict", isinstance(r.statistics, dict))
    check("snapshots is list", isinstance(r.snapshots, list))
    check("alerts is list", isinstance(r.alerts, list))
    check("recommendations is list", isinstance(r.recommendations, list))

    # Verify JSON roundtrip preserves types
    d = r.to_dict()
    r2 = SessionRecord.from_dict(d)
    check("roundtrip types preserved", type(r2.session_id) == str)
    check("roundtrip statistics is dict", type(r2.statistics) == dict)
    check("roundtrip snapshots is list", type(r2.snapshots) == list)

    # Verify repository interface matches SQL pattern
    from backend.persistence.repository import SessionRepository
    methods = ["save", "load", "list_sessions", "delete"]
    for m in methods:
        check(f"repository has {m}()", hasattr(SessionRepository, m))


if __name__ == "__main__":
    print("=" * 70)
    print("  SESSION PERSISTENCE LAYER — COMPREHENSIVE TEST SUITE")
    print("=" * 70)

    test_session_record()
    test_json_repository_crud()
    test_corrupted_file()
    test_large_session()
    test_engine_export()
    test_persistence_service()
    test_service_auto_end()
    test_service_no_session()
    test_json_file_structure()
    test_performance()
    test_migration_path()

    print()
    print("-" * 70)
    total = passed + failed
    print(f"  Result: {passed}/{total} tests passed")
    if failed > 0:
        print(f"  {failed} tests FAILED")
    else:
        print("  All tests PASSED")
    print("-" * 70)
