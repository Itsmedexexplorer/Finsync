"""Unit tests for Database Schema Migrations."""

import pytest
from backend.storage.config import StorageSettings
from backend.storage.database import DatabaseEngine
from backend.storage.migrations import run_migrations


def test_migrations_runner_idempotent():
    settings = StorageSettings(database_url="sqlite:///:memory:")
    engine = DatabaseEngine(settings)
    engine.initialize()

    with engine.get_connection() as conn:
        # Running migrations again should be a no-op
        applied = run_migrations(conn)
        assert applied == []

        # Verify all 18 tables exist
        tables = [
            "cases", "evidence", "claims", "entities", "transactions",
            "match_relationships", "deduplication_groups", "discrepancies",
            "reconciliation_results", "truth_reports", "controller_decisions",
            "reviews", "review_notes", "evidence_inspections",
            "audit_events", "case_assignments", "portfolio_states",
            "idempotency_records",
        ]
        for tbl in tables:
            cur = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tbl}';")
            assert cur.fetchone() is not None, f"Table {tbl} missing from schema"

    engine.shutdown()
