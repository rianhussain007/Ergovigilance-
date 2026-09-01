"""Database query performance monitoring.

Logs slow queries, tracks query statistics, and provides performance insights.
Integrates with SQLite's built-in profiling capabilities.

Configurable via environment:
- SLOW_QUERY_THRESHOLD_MS: queries slower than this are logged (default 100)
- QUERY_MONITOR_ENABLED: enable/disable (default true)

Usage:
    from app.core.query_monitor import query_monitor
    query_monitor.log_query("SELECT * FROM workers", duration_ms=150, rows=50)
    stats = query_monitor.get_stats()
"""

import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

SLOW_QUERY_THRESHOLD_MS = int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "100"))
QUERY_MONITOR_ENABLED = os.getenv("QUERY_MONITOR_ENABLED", "true").lower() == "true"


@dataclass
class QueryStats:
    """Statistics for a single query pattern."""
    query_pattern: str
    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float('inf')
    max_ms: float = 0.0
    last_executed: float = 0.0
    slow_count: int = 0

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.count if self.count > 0 else 0.0


class QueryMonitor:
    """Track and log database query performance."""

    def __init__(self):
        self._stats: dict[str, QueryStats] = {}
        self._total_queries = 0
        self._slow_queries = 0
        self._total_time_ms = 0.0

    def _normalize_query(self, query: str) -> str:
        """Normalize query for pattern grouping (strip literal values)."""
        import re
        # Replace string literals
        normalized = re.sub(r"'[^']*'", "'?'", query)
        # Replace numeric literals
        normalized = re.sub(r'\b\d+\b', '?', normalized)
        # Normalize whitespace
        normalized = ' '.join(normalized.split())
        return normalized[:200]  # Truncate long queries

    def log_query(
        self,
        query: str,
        duration_ms: float,
        rows: int = 0,
        error: Optional[str] = None,
    ) -> None:
        """Log a query execution."""
        if not QUERY_MONITOR_ENABLED:
            return

        self._total_queries += 1
        self._total_time_ms += duration_ms

        pattern = self._normalize_query(query)

        if pattern not in self._stats:
            self._stats[pattern] = QueryStats(query_pattern=pattern)

        stats = self._stats[pattern]
        stats.count += 1
        stats.total_ms += duration_ms
        stats.min_ms = min(stats.min_ms, duration_ms)
        stats.max_ms = max(stats.max_ms, duration_ms)
        stats.last_executed = time.time()

        # Log slow queries
        if duration_ms > SLOW_QUERY_THRESHOLD_MS:
            self._slow_queries += 1
            stats.slow_count += 1
            logger.warning(
                "Slow query (%.1fms, %d rows): %s",
                duration_ms, rows, query[:200]
            )

        # Log errors
        if error:
            logger.error("Query error: %s — %s", error, query[:200])

    def get_stats(self) -> dict:
        """Get query performance statistics."""
        # Sort by total time (most expensive first)
        sorted_stats = sorted(
            self._stats.values(),
            key=lambda s: s.total_ms,
            reverse=True
        )[:20]  # Top 20

        return {
            "enabled": QUERY_MONITOR_ENABLED,
            "total_queries": self._total_queries,
            "slow_queries": self._slow_queries,
            "total_time_ms": round(self._total_time_ms, 1),
            "avg_query_ms": round(
                self._total_time_ms / self._total_queries if self._total_queries > 0 else 0, 1
            ),
            "slow_threshold_ms": SLOW_QUERY_THRESHOLD_MS,
            "top_queries": [
                {
                    "pattern": s.query_pattern[:100],
                    "count": s.count,
                    "avg_ms": round(s.avg_ms, 1),
                    "total_ms": round(s.total_ms, 1),
                    "max_ms": round(s.max_ms, 1),
                    "slow_count": s.slow_count,
                }
                for s in sorted_stats
            ],
        }

    def reset(self) -> None:
        """Reset all statistics."""
        self._stats.clear()
        self._total_queries = 0
        self._slow_queries = 0
        self._total_time_ms = 0.0


# Singleton instance
query_monitor = QueryMonitor()
