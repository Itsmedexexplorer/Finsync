"""VERITY Database Engine & Connection Pool Manager (Day 16).

Provides thread-safe connection pooling, explicit transaction boundaries,
nested savepoints, connection cleanup, health checks, and lifecycle helpers.
"""

from __future__ import annotations

import logging
import queue
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Generator, Optional, Union

from backend.storage.config import StorageSettings, get_storage_settings

logger = logging.getLogger("verity.storage")


class DatabaseConnection:
    """Thread-safe wrapper around a raw database connection with helper execution methods."""

    def __init__(self, raw_conn: sqlite3.Connection, engine: "DatabaseEngine", in_memory: bool = False) -> None:
        self.raw = raw_conn
        self.engine = engine
        self.in_memory = in_memory
        self.created_at = time.time()
        self.is_closed = False

    def execute(self, sql: str, params: Optional[Union[tuple, list, dict]] = None) -> sqlite3.Cursor:
        """Executes a SQL query with optional parameters."""
        if self.engine.settings.echo:
            logger.debug(f"[SQL] {sql} | params={params}")
        if params is None:
            return self.raw.execute(sql)
        return self.raw.execute(sql, params)

    def executemany(self, sql: str, seq_of_params: list) -> sqlite3.Cursor:
        """Executes a SQL statement against multiple parameter sets."""
        if self.engine.settings.echo:
            logger.debug(f"[SQL_MANY] {sql} | batch_size={len(seq_of_params)}")
        return self.raw.executemany(sql, seq_of_params)

    def commit(self) -> None:
        """Commits the current transaction."""
        self.raw.commit()

    def rollback(self) -> None:
        """Rolls back the current transaction."""
        self.raw.rollback()

    def close(self) -> None:
        """Closes the underlying connection."""
        if not self.is_closed:
            try:
                self.raw.close()
            except Exception:
                pass
            self.is_closed = True


class DatabaseEngine:
    """Thread-safe database engine supporting connection pooling and atomic transactions."""

    def __init__(self, settings: Optional[StorageSettings] = None) -> None:
        self.settings = settings or get_storage_settings()
        self._pool: queue.Queue[DatabaseConnection] = queue.Queue(maxsize=self.settings.pool_size + self.settings.max_overflow)
        self._all_connections: list[DatabaseConnection] = []
        self._lock = threading.RLock()
        self._is_initialized = False
        self._is_shutdown = False
        self._shared_memory_conn: Optional[DatabaseConnection] = None
        self._instance_id = uuid.uuid4().hex
        self._parse_url()

    def _parse_url(self) -> None:
        """Parses connection string and configures SQLite paths."""
        url = self.settings.database_url
        if url.startswith("sqlite:///"):
            self.dialect = "sqlite"
            path_part = url[len("sqlite:///"):]
            if path_part == ":memory:" or path_part == "":
                self.db_path = ":memory:"
                self.is_memory = True
            else:
                self.db_path = str(Path(path_part).resolve())
                self.is_memory = False
        elif url.startswith("sqlite://"):
            self.dialect = "sqlite"
            self.db_path = ":memory:"
            self.is_memory = True
        else:
            # Fallback to SQLite if unsupported dialect provided
            self.dialect = "sqlite"
            self.db_path = "data/verity.db"
            self.is_memory = False

    def _create_raw_connection(self) -> DatabaseConnection:
        """Creates and configures a fresh database connection."""
        if self.is_memory:
            # For in-memory, if we already have a shared in-memory connection, reuse or create URI shared cache
            raw = sqlite3.connect(
                f"file:verity_mem_{self._instance_id}?mode=memory&cache=shared",
                uri=True,
                timeout=self.settings.timeout,
                check_same_thread=False,
            )
        else:
            # Ensure parent directories exist
            parent = Path(self.db_path).parent
            parent.mkdir(parents=True, exist_ok=True)
            raw = sqlite3.connect(self.db_path, timeout=self.settings.timeout, check_same_thread=False)

        raw.row_factory = sqlite3.Row

        # Configure SQLite pragmas for safety, speed, and integrity
        raw.execute("PRAGMA foreign_keys = ON;")
        if not self.is_memory:
            try:
                raw.execute("PRAGMA journal_mode = WAL;")
                raw.execute("PRAGMA synchronous = NORMAL;")
            except Exception:
                pass
        raw.execute(f"PRAGMA busy_timeout = {int(self.settings.timeout * 1000)};")

        conn = DatabaseConnection(raw, self, in_memory=self.is_memory)
        with self._lock:
            self._all_connections.append(conn)
        return conn

    def initialize(self) -> None:
        """Initializes database, runs schema migrations, and prepares connection pool."""
        with self._lock:
            if self._is_initialized:
                return

            self._is_initialized = True

            if self.is_memory:
                # Keep one primary in-memory connection open so in-memory DB persists for engine lifetime
                self._shared_memory_conn = self._create_raw_connection()

            # Run initial migrations using direct connection
            mig_conn = self._shared_memory_conn or self._create_raw_connection()
            try:
                from backend.storage.migrations import run_migrations
                run_migrations(mig_conn)
            finally:
                if not self.is_memory:
                    mig_conn.close()

            # Pre-warm pool
            for _ in range(min(2, self.settings.pool_size)):
                conn = self._create_raw_connection()
                self._pool.put(conn)

            logger.info(f"Database initialized successfully (dialect={self.dialect}, path={self.db_path})")

    def shutdown(self) -> None:
        """Closes all connections in pool and releases resources."""
        with self._lock:
            self._is_shutdown = True
            while not self._pool.empty():
                try:
                    conn = self._pool.get_nowait()
                    conn.close()
                except Exception:
                    pass

            for conn in list(self._all_connections):
                try:
                    conn.close()
                except Exception:
                    pass
            self._all_connections.clear()
            if self._shared_memory_conn:
                try:
                    self._shared_memory_conn.close()
                except Exception:
                    pass
                self._shared_memory_conn = None
            self._is_initialized = False
            logger.info("Database shutdown complete.")

    @contextmanager
    def get_connection(self) -> Generator[DatabaseConnection, None, None]:
        """Provides a managed database connection from pool with automatic return."""
        if not self._is_initialized and not self._is_shutdown:
            self.initialize()

        conn: Optional[DatabaseConnection] = None
        try:
            try:
                conn = self._pool.get_nowait()
            except queue.Empty:
                conn = self._create_raw_connection()

            yield conn
        finally:
            if conn and not conn.is_closed and not self._is_shutdown:
                try:
                    self._pool.put_nowait(conn)
                except queue.Full:
                    conn.close()

    def connection(self) -> Generator[DatabaseConnection, None, None]:
        """Alias for get_connection context manager."""
        return self.get_connection()

    @contextmanager
    def transaction(self, existing_conn: Optional[DatabaseConnection] = None) -> Generator[DatabaseConnection, None, None]:
        """Atomic transaction context manager supporting nested savepoints.
        
        If an existing connection is supplied, creates a nested SAVEPOINT.
        Otherwise, borrows a connection, starts a transaction with BEGIN, commits on success,
        and rolls back everything on error.
        """
        if existing_conn is not None:
            # Nested savepoint
            sp_name = f"sp_{uuid.uuid4().hex[:8]}"
            existing_conn.execute(f"SAVEPOINT {sp_name}")
            try:
                yield existing_conn
                existing_conn.execute(f"RELEASE SAVEPOINT {sp_name}")
            except Exception as e:
                try:
                    existing_conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                except Exception:
                    pass
                raise e
        else:
            with self.get_connection() as conn:
                # Explicit transaction start
                conn.execute("BEGIN IMMEDIATE")
                try:
                    yield conn
                    conn.commit()
                except Exception as e:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    raise e

    def check_health(self) -> Dict[str, Any]:
        """Performs live connectivity, latency, and integrity check."""
        start = time.perf_counter()
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("SELECT 1 AS alive, datetime('now') AS db_time")
                row = cursor.fetchone()
                latency_ms = (time.perf_counter() - start) * 1000.0
                return {
                    "status": "HEALTHY",
                    "dialect": self.dialect,
                    "database_path": ":memory:" if self.is_memory else str(self.db_path),
                    "latency_ms": round(latency_ms, 2),
                    "pool_size": self._pool.qsize(),
                    "total_connections": len(self._all_connections),
                    "db_timestamp": row["db_time"] if row else None,
                }
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000.0
            return {
                "status": "UNHEALTHY",
                "error": str(e),
                "dialect": self.dialect,
                "latency_ms": round(latency_ms, 2),
            }


# Singleton database engine provider
_GLOBAL_ENGINE: Optional[DatabaseEngine] = None
_GLOBAL_ENGINE_LOCK = threading.RLock()


def get_database_engine(settings: Optional[StorageSettings] = None) -> DatabaseEngine:
    """Returns singleton DatabaseEngine instance."""
    global _GLOBAL_ENGINE
    with _GLOBAL_ENGINE_LOCK:
        if _GLOBAL_ENGINE is None:
            _GLOBAL_ENGINE = DatabaseEngine(settings)
            _GLOBAL_ENGINE.initialize()
        return _GLOBAL_ENGINE


def reset_database_engine() -> None:
    """Resets global engine (used in test fixtures for isolation)."""
    global _GLOBAL_ENGINE
    with _GLOBAL_ENGINE_LOCK:
        if _GLOBAL_ENGINE is not None:
            _GLOBAL_ENGINE.shutdown()
            _GLOBAL_ENGINE = None


@contextmanager
def get_db_session() -> Generator[DatabaseConnection, None, None]:
    """Convenience dependency generator providing a database connection."""
    engine = get_database_engine()
    with engine.get_connection() as conn:
        yield conn
