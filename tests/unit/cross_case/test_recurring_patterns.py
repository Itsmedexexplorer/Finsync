"""Unit tests for Recurring Discrepancy Patterns (Day 18)."""

import os
import tempfile
import pytest

from backend.cross_case.service import CrossCaseIntelligenceService
from backend.storage.config import StorageSettings
from backend.storage.database import DatabaseEngine
from backend.storage.models import (
    CaseRecord,
    DiscrepancyRecord,
    EntityRecord,
    ReconciliationRecordModel,
)
from backend.storage.repositories.sql.case import SQLCaseRepository
from backend.storage.repositories.sql.discrepancy import SQLDiscrepancyRepository
from backend.storage.repositories.sql.entity import SQLEntityRepository
from backend.storage.repositories.sql.reconciliation import SQLReconciliationRepository


@pytest.fixture
def test_engine():
    temp_dir = tempfile.mkdtemp(prefix="verity_test_disc_")
    db_path = os.path.join(temp_dir, "test_disc.db")
    settings = StorageSettings(database_url=f"sqlite:///{db_path}", pool_size=3)
    engine = DatabaseEngine(settings=settings)
    engine.initialize()
    yield engine
    engine.shutdown()


def test_recurring_discrepancy_pattern_detection(test_engine):
    service = CrossCaseIntelligenceService(engine=test_engine)

    with test_engine.transaction() as conn:
        case_repo = SQLCaseRepository(conn)
        ent_repo = SQLEntityRepository(conn)
        disc_repo = SQLDiscrepancyRepository(conn)
        recon_repo = SQLReconciliationRepository(conn)

        for i in (1, 2):
            cid = f"CASE-DISC-{i}"
            case_repo.create(CaseRecord(case_id=cid, status="PARTIAL"))
            ent_repo.create(EntityRecord(
                id=f"ENT-{i}",
                case_id=cid,
                canonical_name="Delta Services",
            ))
            recon_repo.create(ReconciliationRecordModel(
                reconciliation_id=f"REC-{i}",
                case_id=cid,
                status="PARTIAL",
                expected_amount=20000.0,
                explanation="Discrepancy",
            ))
            disc_repo.create(DiscrepancyRecord(
                id=f"DISC-{i}",
                case_id=cid,
                discrepancy_type="AMOUNT_MISMATCH",
                severity="WARNING",
                message=f"Invoice #{i} amount exceeds bank deposit by INR 2,000",
            ))

    patterns = service.get_recurring_discrepancies(entity_name="Delta Services")
    assert len(patterns) >= 1
    p = patterns[0]
    assert p.discrepancy_type == "AMOUNT_MISMATCH"
    assert p.occurrence_count == 2
    assert "CASE-DISC-1" in p.affected_case_ids
    assert "CASE-DISC-2" in p.affected_case_ids
    assert p.total_affected_exposure == 40000.0
