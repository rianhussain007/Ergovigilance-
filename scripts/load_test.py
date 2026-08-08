"""Lightweight concurrent load test for the ErgoVigilance API.

Hits the core HTTP endpoints (health, login, dashboard, cameras) with a
configurable concurrency/rate and reports latency percentiles, throughput and
error rate. Uses only the standard library + requests (already a dependency)
so it runs anywhere Python runs.

Usage:
    venv/Scripts/python.exe scripts/load_test.py --base http://127.0.0.1:8000 \
        --workers 8 --duration 15 --per-second 20

Auth: reads ADMIN credentials from --user/--pass (defaults to the seeded
admin@example.local / AdminPass123!). Login is performed once and the bearer
token is reused for the authed endpoints.
"""

from __future__ import annotations

import argparse
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import requests

ENDPOINTS = {
    "healthz": lambda tok: ("/healthz", {}),
    "health": lambda tok: ("/health", {}),
    "dashboard": lambda tok: ("/api/dashboard", {"headers": _auth(tok)}),
    "cameras": lambda tok: ("/api/cameras", {"headers": _auth(tok)}),
    "sessions": lambda tok: ("/api/sessions", {"headers": _auth(tok)}),
}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(base: str, user: str, password: str) -> str:
    resp = requests.post(
        f"{base}/api/auth/login",
        json={"email": user, "password": password},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _make_runner(base: str, token: str, endpoint: str) -> Callable[[], float]:
    path, kwargs = ENDPOINTS[endpoint](token)

    def run() -> float:
        start = time.perf_counter()
        try:
            resp = requests.get(f"{base}{path}", timeout=10, **kwargs)
            resp.raise_for_status()
            ok = True
        except Exception:  # noqa: BLE001 - any failure counts as error
            ok = False
        elapsed = (time.perf_counter() - start) * 1000
        return elapsed if ok else -1.0

    return run


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--user", default="admin@example.local")
    ap.add_argument("--password", default="AdminPass123!")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--duration", type=int, default=15, help="seconds")
    ap.add_argument("--per-second", type=float, default=20.0, help="target req/s")
    ap.add_argument("--endpoint", choices=sorted(ENDPOINTS), default="health")
    args = ap.parse_args()

    print(f"Logging in as {args.user} …")
    token = _login(args.base, args.user, args.password)
    runner = _make_runner(args.base, token, args.endpoint)

    latencies: list[float] = []
    errors = 0
    lock = threading.Lock()
    stop = threading.Event()
    interval = 1.0 / args.per_second

    def worker() -> None:
        nonlocal errors
        while not stop.is_set():
            ms = runner()
            with lock:
                if ms < 0:
                    errors += 1
                else:
                    latencies.append(ms)
            time.sleep(interval)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(worker) for _ in range(args.workers)]
        time.sleep(args.duration)
        stop.set()
        for f in futures:
            f.result()

    n = len(latencies)
    if n == 0:
        print("No successful requests recorded.")
        return
    latencies.sort()
    p50 = latencies[min(n - 1, int(n * 0.50))]
    p95 = latencies[min(n - 1, int(n * 0.95))]
    p99 = latencies[min(n - 1, int(n * 0.99))]
    rps = n / args.duration
    print(f"\nEndpoint: /{args.endpoint}  workers={args.workers}  duration={args.duration}s")
    print(f"  requests: {n}   errors: {errors}   error rate: {100 * errors / max(1, n + errors):.2f}%")
    print(f"  throughput: {rps:.1f} req/s")
    print(f"  latency:  p50 {p50:.0f} ms | p95 {p95:.0f} ms | p99 {p99:.0f} ms | max {latencies[-1]:.0f} ms")


if __name__ == "__main__":
    main()
