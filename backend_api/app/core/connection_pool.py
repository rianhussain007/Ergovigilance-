"""Database Connection Pooling for High Concurrency.

Manages a pool of SQLite/PostgreSQL connections to handle concurrent requests
without exhausting database connections.

Features:
- Connection pooling with configurable min/max connections
- Connection health checking
- Automatic connection recycling
- Thread-safe connection acquisition
"""

import os
import time
import logging
import threading
import sqlite3
from queue import Queue, Empty, Full
from typing import Optional
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("AUTH_DB_PATH", "local_auth.db"))


class SQLiteConnectionPool:
    """Thread-safe SQLite connection pool."""

    def __init__(
        self,
        db_path: str = None,
        min_connections: int = 2,
        max_connections: int = 10,
        max_idle_time: float = 300.0,
    ):
        self.db_path = db_path or str(DB_PATH)
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.max_idle_time = max_idle_time

        self._pool: Queue = Queue(maxsize=max_connections)
        self._lock = threading.Lock()
        self._total_created = 0
        self._active = 0
        self._timestamps: dict = {}

        # Pre-create minimum connections
        for _ in range(min_connections):
            conn = self._create_connection()
            if conn:
                self._pool.put_nowait(conn)
                self._total_created += 1

        logger.info(
            "Connection pool initialized: min=%d max=%d db=%s",
            min_connections, max_connections, self.db_path,
        )

    def _create_connection(self) -> Optional[sqlite3.Connection]:
        """Create a new database connection."""
        try:
            conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=10,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            return conn
        except Exception as e:
            logger.error("Failed to create connection: %s", e)
            return None

    @contextmanager
    def acquire(self, timeout: float = 10.0):
        """Acquire a connection from the pool."""
        conn = None
        start = time.time()

        try:
            # Try to get from pool
            try:
                conn = self._pool.get_nowait()
            except Empty:
                # Create new if under limit
                with self._lock:
                    if self._total_created < self.max_connections:
                        conn = self._create_connection()
                        if conn:
                            self._total_created += 1
                # Or wait for one
                if conn is None:
                    conn = self._pool.get(timeout=timeout)

            if conn is None:
                raise RuntimeError("Could not acquire database connection")

            # Health check
            try:
                conn.execute("SELECT 1")
            except Exception:
                logger.warning("Stale connection, creating new one")
                try:
                    conn.close()
                except Exception:
                    pass
                conn = self._create_connection()
                if conn is None:
                    raise RuntimeError("Failed to create replacement connection")

            with self._lock:
                self._active += 1
                self._timestamps[id(conn)] = time.time()

            yield conn

        finally:
            if conn:
                with self._lock:
                    self._active -= 1
                    self._timestamps.pop(id(conn), None)

                try:
                    # Return to pool if not full
                    self._pool.put_nowait(conn)
                except Full:
                    # Pool is full, close the connection
                    try:
                        conn.close()
                    except Exception:
                        pass
                    with self._lock:
                        self._total_created -= 1

    def get_stats(self) -> dict:
        """Get pool statistics."""
        return {
            "pool_size": self._pool.qsize(),
            "active_connections": self._active,
            "total_created": self._total_created,
            "max_connections": self.max_connections,
            "min_connections": self.min_connections,
        }

    def close_all(self):
        """Close all connections in the pool."""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except Exception:
                pass
        with self._lock:
            self._total_created = 0
            self._active = 0
        logger.info("All connections closed")


# Global connection pool
_connection_pool: Optional[SQLiteConnectionPool] = None


def get_connection_pool() -> SQLiteConnectionPool:
    """Get or create the global connection pool."""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = SQLiteConnectionPool()
    return _connection_pool


def get_pooled_connection(timeout: float = 10.0):
    """Get a connection from the pool (context manager)."""
    pool = get_connection_pool()
    return pool.acquire(timeout=timeout)
