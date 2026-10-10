"""Unit tests for PersistentAuditStore with SHA-256 Hash Chaining."""

import pytest
from backend.storage.audit_store import GENESIS_HASH, PersistentAuditStore
from backend.storage.config import StorageSettings
from backend.storage.database import DatabaseEngine
from backend.storage.models import CaseRecord
from backend.storage.repositories.sql.case import SQLCaseRepository


@pytest.fixture
def audit_store_engine():
    settings = StorageSettings(database_url="sqlite:///:memory:")
    engine = DatabaseEngine(settings)
    engine.initialize()
    with engine.transaction() as conn:
        SQLCaseRepository(conn).create(CaseRecord(case_id="AUDIT-CASE-01", status="CONFIRMED"))
    store = PersistentAuditStore(engine)
    yield store, engine
    engine.shutdown()


def test_audit_hash_chain_creation_and_verification(audit_store_engine):
    store, engine = audit_store_engine

    ev1 = store.append_event(
        case_id="AUDIT-CASE-01",
        event_type="CASE_PROCESSED",
        actor_id="system",
        description="Case processed",
    )
    assert ev1.sequence_number == 1
    assert ev1.previous_state_hash == GENESIS_HASH

    ev2 = store.append_event(
        case_id="AUDIT-CASE-01",
        event_type="NOTE_ADDED",
        actor_id="ctrl_alice",
        description="Added audit note",
    )
    assert ev2.sequence_number == 2
    assert ev2.previous_state_hash == ev1.current_state_hash

    is_valid, errors = store.verify_chain("AUDIT-CASE-01")
    assert is_valid is True
    assert len(errors) == 0


def test_audit_tamper_detection(audit_store_engine):
    store, engine = audit_store_engine

    ev1 = store.append_event(
        case_id="AUDIT-CASE-01",
        event_type="CASE_PROCESSED",
        actor_id="system",
        description="Initial event",
    )

    # Tamper with database row
    with engine.get_connection() as conn:
        conn.execute(
            "UPDATE audit_events SET description = 'TAMPERED' WHERE event_id = ?;",
            (ev1.event_id,),
        )
        conn.commit()

    is_valid, errors = store.verify_chain("AUDIT-CASE-01")
    assert is_valid is False
    assert len(errors) > 0
    assert "Tampered state hash" in errors[0]
