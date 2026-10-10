"""Unit tests for DatabaseEngine, Connection Pooling, and Transactions."""

import sqlite3
import pytest
from backend.storage.config import StorageSettings
from backend.storage.database import DatabaseEngine


@pytest.fixture
def memory_engine():
    settings = StorageSettings(database_url="sqlite:///:memory:")
    engine = DatabaseEngine(settings)
    engine.initialize()
    yield engine
    engine.shutdown()


def test_database_engine_initialization(memory_engine):
    assert memory_engine.is_memory is True
    assert memory_engine._is_initialized is True
    health = memory_engine.check_health()
    assert health["status"] == "HEALTHY"
    assert health["dialect"] == "sqlite"


def test_transaction_commit(memory_engine):
    with memory_engine.transaction() as conn:
        conn.execute("INSERT INTO cases (case_id, status, confidence_score) VALUES (?, ?, ?);", ("C1", "CONFIRMED", 1.0))

    with memory_engine.get_connection() as conn:
        cur = conn.execute("SELECT * FROM cases WHERE case_id = ?;", ("C1",))
        row = cur.fetchone()
        assert row is not None
        assert row["case_id"] == "C1"


def test_transaction_rollback_on_exception(memory_engine):
    try:
        with memory_engine.transaction() as conn:
            conn.execute("INSERT INTO cases (case_id, status, confidence_score) VALUES (?, ?, ?);", ("C2", "CONFIRMED", 1.0))
            raise RuntimeError("Simulated transaction abort")
    except RuntimeError:
        pass

    with memory_engine.get_connection() as conn:
        cur = conn.execute("SELECT * FROM cases WHERE case_id = ?;", ("C2",))
        row = cur.fetchone()
        assert row is None


def test_nested_transaction_savepoints(memory_engine):
    with memory_engine.transaction() as conn:
        conn.execute("INSERT INTO cases (case_id, status, confidence_score) VALUES (?, ?, ?);", ("C3", "CONFIRMED", 1.0))
        try:
            with memory_engine.transaction(conn) as nested_conn:
                nested_conn.execute("INSERT INTO cases (case_id, status, confidence_score) VALUES (?, ?, ?);", ("C4", "CONTRADICTED", 0.8))
                raise ValueError("Rollback inner savepoint only")
        except ValueError:
            pass

    with memory_engine.get_connection() as conn:
        # C3 committed, C4 rolled back
        assert conn.execute("SELECT * FROM cases WHERE case_id = 'C3';").fetchone() is not None
        assert conn.execute("SELECT * FROM cases WHERE case_id = 'C4';").fetchone() is None
