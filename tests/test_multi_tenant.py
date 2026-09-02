"""Tests for multi-tenant data isolation.

Verifies that organizations cannot see each other's data:
- Workers belong to their org only
- Alerts belong to their org only
- Audit logs belong to their org only
"""

import pytest
import sys
import os

# Ensure backend_api is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend_api"))


@pytest.fixture(autouse=True)
def _ensure_db():
    """Ensure the database is initialized with migrations."""
    from app.core.database import init_local_database
    init_local_database()


class TestMultiTenantIsolation:
    """Test that organizations are properly isolated from each other."""

    def test_organizations_exist(self):
        """Both demo organizations exist in the database."""
        from app.core.database import get_connection

        with get_connection() as conn:
            orgs = conn.execute("SELECT slug, name, plan FROM organizations ORDER BY slug").fetchall()
            slugs = {o[0] for o in orgs}

            assert "demo-factory" in slugs, "Demo Factory org missing"
            assert "acme-mfg" in slugs, "Acme Manufacturing org missing"

            print(f"  Organizations: {[o[0] for o in orgs]}")

    def test_users_belong_to_orgs(self):
        """All users belong to an organization."""
        from app.core.database import get_connection

        with get_connection() as conn:
            users = conn.execute("SELECT email, org_id FROM users").fetchall()
            for email, org_id in users:
                assert org_id is not None, f"User {email} has no org_id"

            print(f"  All {len(users)} users belong to an organization")

    def test_org_scoped_workers(self):
        """Workers filtered by org_id return only that org's workers."""
        from app.core.database import list_workers, get_connection

        with get_connection() as conn:
            orgs = conn.execute("SELECT id, slug FROM organizations ORDER BY id").fetchall()
            assert len(orgs) >= 2, "Need at least 2 demo organizations"

            org_a_id = orgs[0][0]
            org_b_id = orgs[1][0]

            workers_a = list_workers(org_id=org_a_id)
            workers_b = list_workers(org_id=org_b_id)

            ids_a = {w["worker_id"] for w in workers_a}
            ids_b = {w["worker_id"] for w in workers_b}

            overlap = ids_a & ids_b
            assert len(overlap) == 0, f"Orgs share workers: {overlap}"

            print(f"  Org {org_a_id}: {len(workers_a)} workers")
            print(f"  Org {org_b_id}: {len(workers_b)} workers")
            print(f"  Overlap: {len(overlap)} (should be 0)")

    def test_org_scoped_alerts(self):
        """Alerts filtered by org_id return only that org's alerts."""
        from app.core.database import load_active_alerts, get_connection

        with get_connection() as conn:
            orgs = conn.execute("SELECT id, slug FROM organizations ORDER BY id").fetchall()
            assert len(orgs) >= 2

            org_a_id = orgs[0][0]
            org_b_id = orgs[1][0]

            alerts_a = load_active_alerts(org_id=org_a_id)
            alerts_b = load_active_alerts(org_id=org_b_id)

            ids_a = {a["id"] for a in alerts_a}
            ids_b = {a["id"] for a in alerts_b}

            overlap = ids_a & ids_b
            assert len(overlap) == 0, f"Orgs share alerts: {overlap}"

            print(f"  Org {org_a_id}: {len(alerts_a)} alerts")
            print(f"  Org {org_b_id}: {len(alerts_b)} alerts")

    def test_org_scoped_audit_log(self):
        """Audit log filtered by org_id returns only that org's entries."""
        from app.core.database import load_audit_log, get_connection

        with get_connection() as conn:
            orgs = conn.execute("SELECT id, slug FROM organizations ORDER BY id").fetchall()
            assert len(orgs) >= 2

            org_a_id = orgs[0][0]
            org_b_id = orgs[1][0]

            log_a = load_audit_log(org_id=org_a_id)
            log_b = load_audit_log(org_id=org_b_id)

            ids_a = {e["id"] for e in log_a}
            ids_b = {e["id"] for e in log_b}

            overlap = ids_a & ids_b
            assert len(overlap) == 0, f"Orgs share audit entries: {overlap}"

            print(f"  Org {org_a_id}: {len(log_a)} audit entries")
            print(f"  Org {org_b_id}: {len(log_b)} audit entries")

    def test_org_scoped_query_filter(self):
        """The filter_query utility adds WHERE org_id correctly."""
        from app.core.tenant import filter_query

        # No org_id — no filter
        query, params = filter_query("SELECT * FROM alerts", None)
        assert "org_id" not in query
        assert params == []

        # With org_id — adds filter
        query, params = filter_query("SELECT * FROM alerts", 42)
        assert "org_id" in query
        assert 42 in params

        # Existing WHERE clause — uses AND
        query, params = filter_query("SELECT * FROM alerts WHERE state = 'ACTIVE'", 42)
        assert "AND org_id" in query
        assert 42 in params

        print("  filter_query works correctly")
