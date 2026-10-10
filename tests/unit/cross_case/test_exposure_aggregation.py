"""Unit tests for Historical Exposure Aggregation (Day 18)."""

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
    temp_dir = tempfile.mkdtemp(prefix="verity_test_exp_")
    db_path = os.path.join(temp_dir, "test_exp.db")
    settings = StorageSettings(database_url=f"sqlite:///{db_path}", pool_size=3)
    engine = DatabaseEngine(settings=settings)
    engine.initialize()
    yield engine
    engine.shutdown()


def test_exposure_aggregation_with_disputes_and_unresolved(test_engine):
    service = CrossCaseIntelligenceService(engine=test_engine)

    with test_engine.transaction() as conn:
        case_repo = SQLCaseRepository(conn)
        ent_repo = SQLEntityRepository(conn)
        recon_repo = SQLReconciliationRepository(conn)

        # 3 cases for Global Tech:
        # Case 1: Confirmed ₹50,000
        # Case 2: Contradicted ₹30,000 (disputed)
        # Case 3: Partial ₹20,000 (matched: 15,000, outstanding: 5,000)
        case_repo.create(CaseRecord(case_id="C1", status="CONFIRMED"))
        case_repo.create(CaseRecord(case_id="C2", status="CONTRADICTED"))
        case_repo.create(CaseRecord(case_id="C3", status="PARTIAL"))

        for cid in ("C1", "C2", "C3"):
            ent_repo.create(EntityRecord(
                id=f"ENT-{cid}",
                case_id=cid,
                canonical_name="Global Tech Solutions",
            ))

        recon_repo.create(ReconciliationRecordModel(
            reconciliation_id="R1",
            case_id="C1",
            status="CONFIRMED",
            expected_amount=50000.0,
            matched_amount=50000.0,
            outstanding_amount=0.0,
            explanation="Exact",
        ))
        recon_repo.create(ReconciliationRecordModel(
            reconciliation_id="R2",
            case_id="C2",
            status="CONTRADICTED",
            expected_amount=30000.0,
            matched_amount=0.0,
            outstanding_amount=30000.0,
            explanation="Disputed",
        ))
        recon_repo.create(ReconciliationRecordModel(
            reconciliation_id="R3",
            case_id="C3",
            status="PARTIAL",
            expected_amount=20000.0,
            matched_amount=15000.0,
            outstanding_amount=5000.0,
            explanation="Partial",
        ))

    history = service.get_counterparty_history("Global Tech Solutions")
    assert history is not None
    assert history.case_count == 3
    assert history.total_exposure == 100000.0
    assert history.disputed_exposure == 30000.0
    assert history.unresolved_exposure == 5000.0
    assert history.contradiction_count == 1
