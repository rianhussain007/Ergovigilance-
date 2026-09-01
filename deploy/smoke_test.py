#!/usr/bin/env python3
"""Production deployment smoke test.

Validates all critical endpoints are working after deployment.
Run this after deploying to verify the system is operational.

Usage:
    python deploy/smoke_test.py --url http://localhost:8001
    python deploy/smoke_test.py --url https://ergovigilance.com --token YOUR_JWT
"""

import argparse
import json
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


class SmokeTest:
    """Run smoke tests against a deployed ErgoVigilance instance."""

    def __init__(self, base_url: str, token: str = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.results = []
        self.passed = 0
        self.failed = 0

    def _request(self, method: str, path: str, data: dict = None, auth: bool = True) -> dict:
        """Make an HTTP request and return response."""
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        body = json.dumps(data).encode() if data else None
        req = Request(url, data=body, headers=headers, method=method)

        try:
            with urlopen(req, timeout=10) as resp:
                return {
                    "status": resp.status,
                    "body": json.loads(resp.read().decode()),
                    "ok": True,
                }
        except HTTPError as e:
            return {
                "status": e.code,
                "body": {},
                "ok": False,
                "error": str(e),
            }
        except URLError as e:
            return {
                "status": 0,
                "body": {},
                "ok": False,
                "error": str(e.reason),
            }

    def test(self, name: str, method: str, path: str, expected_status: int = 200,
             data: dict = None, auth: bool = True) -> bool:
        """Run a single test."""
        start = time.time()
        resp = self._request(method, path, data=data, auth=auth)
        latency_ms = (time.time() - start) * 1000

        passed = resp["ok"] and resp["status"] == expected_status
        status = "✅ PASS" if passed else "❌ FAIL"

        if passed:
            self.passed += 1
        else:
            self.failed += 1

        self.results.append({
            "name": name,
            "passed": passed,
            "status_code": resp["status"],
            "latency_ms": round(latency_ms, 1),
        })

        print(f"  {status}  {name} ({resp['status']}, {latency_ms:.0f}ms)")
        return passed

    def run_all(self) -> bool:
        """Run all smoke tests."""
        print(f"\n🔍 ErgoVigilance Deployment Smoke Test")
        print(f"   Target: {self.base_url}")
        print(f"   Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

        # ── Health Checks ──────────────────────────────────
        print("📋 Health Checks:")
        self.test("Liveness probe", "GET", "/healthz")
        self.test("Readiness probe", "GET", "/readyz")
        self.test("Prometheus metrics", "GET", "/metrics", auth=False)
        self.test("SLA status", "GET", "/sla", auth=False)
        self.test("Storage stats", "GET", "/storage", auth=False)

        # ── Authentication ─────────────────────────────────
        print("\n🔐 Authentication:")
        self.test("Demo login", "POST", "/api/auth/demo", data={}, auth=False)
        self.test("Login endpoint exists", "POST", "/api/auth/login",
                  data={"email": "test@test.com", "password": "wrong"}, expected_status=401, auth=False)

        # ── Login for authenticated tests ──────────────────
        print("\n🔑 Obtaining test token...")
        demo_resp = self._request("POST", "/api/auth/demo", data={}, auth=False)
        if demo_resp["ok"] and "access_token" in demo_resp["body"]:
            self.token = demo_resp["body"]["access_token"]
            print("   ✅ Token obtained\n")
        else:
            print("   ❌ Could not obtain token — skipping authenticated tests\n")
            self._print_summary()
            return False

        # ── Dashboard & Data ───────────────────────────────
        print("📊 Dashboard & Data:")
        self.test("Dashboard KPIs", "GET", "/api/dashboard")
        self.test("Sessions list", "GET", "/api/sessions")
        self.test("Alerts list", "GET", "/api/alerts")
        self.test("Workers list", "GET", "/api/workers")
        self.test("Reports list", "GET", "/api/reports")
        self.test("Search endpoint", "GET", "/api/search?q=operator")
        self.test("Risk trends", "GET", "/api/risk-trend")
        self.test("Analytics overview", "GET", "/api/analytics/overview")

        # ── Live Monitoring ────────────────────────────────
        print("\n🎥 Live Monitoring:")
        self.test("Start session", "POST", "/api/sessions/start",
                  data={"worker_id": "EMP-001"})
        self.test("Active session", "GET", "/api/sessions/active")
        self.test("Stop session", "POST", "/api/sessions/stop")

        # ── Privacy & Compliance ───────────────────────────
        print("\n🔒 Privacy & Compliance:")
        self.test("Audit log entries", "GET", "/api/audit-log?since_hours=24")
        self.test("Audit log stats", "GET", "/api/audit-log/stats")

        # ── Settings ───────────────────────────────────────
        print("\n⚙️  Settings:")
        self.test("User settings", "GET", "/api/settings")
        self.test("System health", "GET", "/api/deployment/health")

        # ── Frontend ───────────────────────────────────────
        print("\n🌐 Frontend:")
        self.test("Frontend loads", "GET", "/", auth=False)

        self._print_summary()
        return self.failed == 0

    def _print_summary(self):
        """Print test summary."""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"📊 Results: {self.passed}/{total} passed, {self.failed} failed")
        print(f"{'='*60}")

        if self.failed > 0:
            print("\n❌ FAILED TESTS:")
            for r in self.results:
                if not r["passed"]:
                    print(f"   - {r['name']} (status: {r['status_code']})")

        avg_latency = sum(r["latency_ms"] for r in self.results) / len(self.results) if self.results else 0
        print(f"\n⏱️  Average latency: {avg_latency:.0f}ms")

        if self.failed == 0:
            print("\n✅ All smoke tests passed — deployment is healthy!")
        else:
            print(f"\n❌ {self.failed} test(s) failed — investigate before going live")


def main():
    parser = argparse.ArgumentParser(description="ErgoVigilance deployment smoke test")
    parser.add_argument("--url", default="http://localhost:8001", help="Backend URL")
    parser.add_argument("--token", help="JWT token for authenticated tests")
    args = parser.parse_args()

    smoke = SmokeTest(args.url, args.token)
    success = smoke.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
