"""Unit tests for Cross-Case Entity History & Counterparty Memory (Day 18)."""

import os
import tempfile
import pytest

from backend.cross_case.service import CrossCaseIntelligenceService
from backend.storage.config import StorageSettings
from backend.storage.database import DatabaseEngine
from backend.storage.models import (
    CaseRecord,
    EntityRecord,
    ReconciliationRecordModel,
)
from backend.storage.repositories.sql.case import SQLCaseRepository
from backend.storage.repositories.sql.entity import SQLEntityRepository
from backend.storage.repositories.sql.reconciliation import SQLReconciliationRepository


@pytest.fixture
def test_engine():
    temp_dir = tempfile.mkdtemp(prefix="verity_test_cross_")
    db_path = os.path.join(temp_dir, "test_cross.db")
    settings = StorageSettings(database_url=f"sqlite:///{db_path}", pool_size=3)
    engine = DatabaseEngine(settings=settings)
    engine.initialize()
    yield engine
    engine.shutdown()


def test_entity_history_lookup(test_engine):
    service = CrossCaseIntelligenceService(engine=test_engine)

    # 1. Seed two cases with the same entity
    with test_engine.transaction() as conn:
        case_repo = SQLCaseRepository(conn)
        ent_repo = SQLEntityRepository(conn)
        recon_repo = SQLReconciliationRepository(conn)

        case_repo.create(CaseRecord(case_id="CASE-E1", status="CONFIRMED"))
        case_repo.create(CaseRecord(case_id="CASE-E2", status="CONFIRMED"))

        ent_repo.create(EntityRecord(
            id="ENT-1",
            case_id="CASE-E1",
            canonical_name="Apex Logistics",
            gstin="27AAPCA1234F1Z5",
            aliases=["Apex"],
        ))
        ent_repo.create(EntityRecord(
            id="ENT-2",
            case_id="CASE-E2",
            canonical_name="Apex Logistics",
            gstin="27AAPCA1234F1Z5",
            aliases=["Apex Cargo"],
        ))

        recon_repo.create(ReconciliationRecordModel(
            reconciliation_id="REC-1",
            case_id="CASE-E1",
            status="CONFIRMED",
            expected_amount=25000.0,
            matched_amount=25000.0,
            explanation="Exact match",
        ))
        recon_repo.create(ReconciliationRecordModel(
            reconciliation_id="REC-2",
            case_id="CASE-E2",
            status="CONFIRMED",
            expected_amount=35000.0,
            matched_amount=35000.0,
            explanation="Exact match",
        ))

    # 2. Query history
    history = service.get_counterparty_history("Apex Logistics")
    assert history is not None
    assert history.canonical_name == "Apex Logistics"
    assert history.case_count == 2
    assert history.total_exposure == 60000.0
    assert "Apex Cargo" in history.aliases or "Apex" in history.aliases
    assert history.gstin == "27AAPCA1234F1Z5"


def test_entity_history_missing(test_engine):
    service = CrossCaseIntelligenceService(engine=test_engine)
    history = service.get_counterparty_history("NonExistent Corp")
    assert history is None
