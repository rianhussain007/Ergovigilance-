"""Load test for ErgoVigilance backend API.

Simulates multiple concurrent camera streams sending pose data
and verifies the backend handles the load without errors.

Usage:
    python tests/load_test.py
    python tests/load_test.py --concurrent 50 --duration 60
    python tests/load_test.py --url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@dataclass
class LoadTestResult:
    """Results from a load test run."""
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    requests_per_second: float = 0.0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


def make_request(url: str, method: str = "GET", data: Any = None, timeout: int = 10) -> tuple[float, bool, str]:
    """Make a single HTTP request and return (latency_ms, success, error)."""
    start = time.perf_counter()
    try:
        if method == "GET":
            resp = requests.get(url, timeout=timeout)
        elif method == "POST":
            resp = requests.post(url, json=data, timeout=timeout)
        else:
            return 0, False, f"Unknown method: {method}"

        latency = (time.perf_counter() - start) * 1000
        success = resp.status_code < 500
        error = "" if success else f"HTTP {resp.status_code}"
        return latency, success, error

    except requests.exceptions.Timeout:
        latency = (time.perf_counter() - start) * 1000
        return latency, False, "Timeout"
    except requests.exceptions.ConnectionError:
        latency = (time.perf_counter() - start) * 1000
        return latency, False, "Connection error"
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return latency, False, str(e)


def run_load_test(
    base_url: str,
    concurrent: int = 50,
    duration: int = 30,
    endpoints: list[dict] | None = None,
) -> LoadTestResult:
    """Run a load test against the backend API.

    Args:
        base_url: Backend API base URL
        concurrent: Number of concurrent workers
        duration: Test duration in seconds
        endpoints: List of endpoint configs to test
    """
    if endpoints is None:
        endpoints = [
            {"path": "/health", "method": "GET", "weight": 3},
            {"path": "/api/dashboard", "method": "GET", "weight": 2},
            {"path": "/api/sessions?limit=10", "method": "GET", "weight": 2},
            {"path": "/api/workers", "method": "GET", "weight": 1},
            {"path": "/api/alerts?limit=10", "method": "GET", "weight": 1},
        ]

    print(f"Starting load test...")
    print(f"  URL: {base_url}")
    print(f"  Concurrent: {concurrent}")
    print(f"  Duration: {duration}s")
    print(f"  Endpoints: {len(endpoints)}")
    print()

    # Build weighted endpoint list
    weighted_endpoints = []
    for ep in endpoints:
        for _ in range(ep.get("weight", 1)):
            weighted_endpoints.append(ep)

    latencies = []
    errors = []
    total_requests = 0
    start_time = time.perf_counter()

    def worker():
        nonlocal total_requests
        while time.perf_counter() - start_time < duration:
            ep = weighted_endpoints[total_requests % len(weighted_endpoints)]
            url = f"{base_url}{ep['path']}"
            latency, success, error = make_request(url, ep["method"])

            if success:
                latencies.append(latency)
            else:
                errors.append(error)

            total_requests += 1

    # Run workers
    with ThreadPoolExecutor(max_workers=concurrent) as executor:
        futures = [executor.submit(worker) for _ in range(concurrent)]
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                errors.append(str(e))

    elapsed = time.perf_counter() - start_time

    # Calculate stats
    result = LoadTestResult()
    result.total_requests = total_requests
    result.successful = len(latencies)
    result.failed = len(errors)
    result.duration_seconds = round(elapsed, 2)
    result.requests_per_second = round(total_requests / elapsed, 1)

    if latencies:
        latencies.sort()
        result.avg_latency_ms = round(sum(latencies) / len(latencies), 1)
        result.p95_latency_ms = round(latencies[int(len(latencies) * 0.95)], 1)
        result.p99_latency_ms = round(latencies[int(len(latencies) * 0.99)], 1)
        result.max_latency_ms = round(max(latencies), 1)

    # Count unique errors
    error_counts = {}
    for e in errors:
        error_counts[e] = error_counts.get(e, 0) + 1
    result.errors = [f"{count}x {err}" for err, count in sorted(error_counts.items(), key=lambda x: -x[1])]

    return result


def print_results(result: LoadTestResult):
    """Print load test results in a formatted table."""
    print()
    print("=" * 60)
    print("LOAD TEST RESULTS")
    print("=" * 60)
    print()
    print(f"  Duration:           {result.duration_seconds}s")
    print(f"  Total Requests:     {result.total_requests}")
    print(f"  Successful:         {result.successful}")
    print(f"  Failed:             {result.failed}")
    print(f"  Requests/sec:       {result.requests_per_second}")
    print()
    print(f"  Avg Latency:        {result.avg_latency_ms}ms")
    print(f"  P95 Latency:        {result.p95_latency_ms}ms")
    print(f"  P99 Latency:        {result.p99_latency_ms}ms")
    print(f"  Max Latency:        {result.max_latency_ms}ms")
    print()

    if result.errors:
        print("  Errors:")
        for err in result.errors[:10]:
            print(f"    - {err}")
    else:
        print("  Errors: None")

    print()

    # Pass/Fail assessment
    pass_criteria = [
        (result.failed / max(result.total_requests, 1)) < 0.05,  # <5% error rate
        result.p95_latency_ms < 500,  # P95 <500ms
        result.requests_per_second > 10,  # >10 req/s
    ]

    if all(pass_criteria):
        print("  PASS - All criteria met")
    else:
        print("  WARN - Some criteria not met:")
        if not pass_criteria[0]:
            print(f"    - Error rate {(result.failed / max(result.total_requests, 1) * 100):.1f}% > 5%")
        if not pass_criteria[1]:
            print(f"    - P95 latency {result.p95_latency_ms}ms > 500ms")
        if not pass_criteria[2]:
            print(f"    - Throughput {result.requests_per_second} req/s < 10")

    print("=" * 60)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="ErgoVigilance load test")
    ap.add_argument("--url", default="http://localhost:8000", help="Backend API URL")
    ap.add_argument("--concurrent", type=int, default=50, help="Concurrent workers")
    ap.add_argument("--duration", type=int, default=30, help="Test duration (seconds)")
    args = ap.parse_args()

    result = run_load_test(args.url, args.concurrent, args.duration)
    print_results(result)
