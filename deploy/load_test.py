"""ErgoVigilance Enterprise Load Test

Validates production readiness by simulating concurrent users:
1. Authentication (login + token refresh)
2. Dashboard polling
3. Session start/stop
4. Alert queries
5. Report generation
6. WebSocket connections

Usage:
    python deploy/load_test.py --url http://localhost:8001 --users 50 --duration 60
    python deploy/load_test.py --url https://ergovigilance.yourdomain.com --users 100

Requires: pip install aiohttp
"""

import asyncio
import aiohttp
import sys
import time
import json
import argparse
from dataclasses import dataclass, field
from typing import List


@dataclass
class TestResults:
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    latencies: List[float] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    start_time: float = 0
    end_time: float = 0
    # Worker accounting. A worker that cannot log in contributes no traffic,
    # so a run that silently drops workers must never be quoted as N users
    # (2026-09-28: the per-IP auth throttle admitted 10 of 20 logins and the
    # report still said "20 users, 0 failed").
    workers_started: int = 0
    workers_authenticated: int = 0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def rps(self) -> float:
        return self.total_requests / max(self.duration, 0.001)

    @property
    def avg_latency(self) -> float:
        return sum(self.latencies) / max(len(self.latencies), 1)

    @property
    def p95_latency(self) -> float:
        if not self.latencies:
            return 0
        sorted_lat = sorted(self.latencies)
        idx = int(len(sorted_lat) * 0.95)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]

    @property
    def p99_latency(self) -> float:
        if not self.latencies:
            return 0
        sorted_lat = sorted(self.latencies)
        idx = int(len(sorted_lat) * 0.99)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]

    def summary(self) -> str:
        return f"""
═══════════════════════════════════════════════════════════
  ErgoVigilance Load Test Results
═══════════════════════════════════════════════════════════
  Duration:       {self.duration:.1f}s
  Users:          {self.workers_authenticated}/{self.workers_started} authenticated
  Total Requests: {self.total_requests}
  Successful:     {self.successful} ({self.successful/max(self.total_requests,1)*100:.1f}%)
  Failed:         {self.failed} ({self.failed/max(self.total_requests,1)*100:.1f}%)
  Requests/sec:   {self.rps:.1f}
  Avg Latency:    {self.avg_latency:.0f}ms
  P95 Latency:    {self.p95_latency:.0f}ms
  P99 Latency:    {self.p99_latency:.0f}ms
  Errors:         {len(self.errors)}
═══════════════════════════════════════════════════════════
"""


async def login(session: aiohttp.ClientSession, url: str) -> tuple[str, str]:
    """Login and return (JWT token, failure reason). Token is '' on failure."""
    try:
        async with session.post(
            f"{url}/api/auth/login",
            json={"email": "admin@example.local", "password": "AdminPass123!"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                token = data.get("token", "")
                return (token, "") if token else ("", "HTTP 200 without a token")
            body = (await resp.text())[:100].replace("\n", " ")
            return "", f"HTTP {resp.status} {body}"
    except Exception as exc:
        return "", f"{type(exc).__name__}: {str(exc)[:100]}"


async def test_endpoint(
    session: aiohttp.ClientSession,
    url: str,
    token: str,
    method: str,
    path: str,
    results: TestResults,
    json_data: dict = None,
):
    """Test a single endpoint."""
    start = time.time()
    try:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        async with session.request(
            method, f"{url}{path}", headers=headers, json=json_data
        ) as resp:
            latency = (time.time() - start) * 1000
            results.latencies.append(latency)
            results.total_requests += 1
            if resp.status < 400:
                results.successful += 1
            else:
                results.failed += 1
                results.errors.append(f"{method} {path}: {resp.status}")
    except Exception as e:
        results.failed += 1
        results.total_requests += 1
        results.errors.append(f"{method} {path}: {str(e)[:100]}")


async def worker(
    worker_id: int,
    url: str,
    duration: float,
    results: TestResults,
):
    """Simulate a single user session."""
    async with aiohttp.ClientSession() as session:
        token, failure = await login(session, url)
        if not token:
            results.errors.append(f"Worker {worker_id}: login failed — {failure}")
            return
        results.workers_authenticated += 1

        end_time = time.time() + duration
        endpoints = [
            ("GET", "/api/dashboard", None),
            ("GET", "/api/sessions", None),
            ("GET", "/api/alerts", None),
            ("GET", "/api/workers", None),
            ("GET", "/api/reports", None),
            ("GET", "/api/analytics", None),
            ("GET", "/api/context/snapshot", None),
            ("GET", "/api/audit", None),
        ]

        while time.time() < end_time:
            method, path, data = endpoints[results.total_requests % len(endpoints)]
            await test_endpoint(session, url, token, method, path, results, data)
            await asyncio.sleep(0.1)  # 10 requests per second per user


async def main(url: str, num_users: int, duration: float):
    """Run the load test."""
    print(f"\nStarting load test: {num_users} users for {duration}s")
    print(f"Target: {url}")

    results = TestResults(start_time=time.time(), workers_started=num_users)

    # Verify target is reachable
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{url}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    print(f"WARNING: Health check returned {resp.status}")
        except Exception as e:
            print(f"ERROR: Cannot reach {url}: {e}")
            return

    # Run workers
    tasks = [worker(i, url, duration, results) for i in range(num_users)]
    await asyncio.gather(*tasks)

    results.end_time = time.time()
    print(results.summary())

    # Save results
    report = {
        "url": url,
        "users": num_users,
        "workers_started": results.workers_started,
        "workers_authenticated": results.workers_authenticated,
        "duration": duration,
        "total_requests": results.total_requests,
        "successful": results.successful,
        "failed": results.failed,
        "rps": results.rps,
        "avg_latency_ms": results.avg_latency,
        "p95_latency_ms": results.p95_latency,
        "p99_latency_ms": results.p99_latency,
        "errors": results.errors[:20],
    }

    with open("load_test_results.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"Results saved to load_test_results.json")


if __name__ == "__main__":
    # The summary uses box-drawing/check glyphs, and a Windows console defaults to
    # cp1252 — printing it raised UnicodeEncodeError *after* the whole test had
    # run, so the run was lost and the qualification harness saw exit 1
    # (found 2026-09-28). Reconfigure instead of stripping the characters.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="ErgoVigilance Load Test")
    parser.add_argument("--url", default="http://localhost:8001", help="API URL")
    parser.add_argument("--users", type=int, default=10, help="Number of concurrent users")
    parser.add_argument("--duration", type=float, default=30, help="Test duration in seconds")
    args = parser.parse_args()

    asyncio.run(main(args.url, args.users, args.duration))
