"""Unit tests for Historical Risk Signals (Day 18)."""

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
    TransactionRecord,
)
from backend.storage.repositories.sql.case import SQLCaseRepository
from backend.storage.repositories.sql.entity import SQLEntityRepository
from backend.storage.repositories.sql.reconciliation import SQLReconciliationRepository
from backend.storage.repositories.sql.transaction import SQLTransactionRepository


@pytest.fixture
def test_engine():
    temp_dir = tempfile.mkdtemp(prefix="verity_test_sig_")
    db_path = os.path.join(temp_dir, "test_sig.db")
    settings = StorageSettings(database_url=f"sqlite:///{db_path}", pool_size=3)
    engine = DatabaseEngine(settings=settings)
    engine.initialize()
    yield engine
    engine.shutdown()


def test_historical_risk_signals_generation(test_engine):
    service = CrossCaseIntelligenceService(engine=test_engine)

    with test_engine.transaction() as conn:
        case_repo = SQLCaseRepository(conn)
        ent_repo = SQLEntityRepository(conn)
        recon_repo = SQLReconciliationRepository(conn)
        txn_repo = SQLTransactionRepository(conn)

        # Historical case with contradiction and duplicate UTR
        case_repo.create(CaseRecord(case_id="PAST-01", status="CONTRADICTED"))
        ent_repo.create(EntityRecord(
            id="ENT-P1",
            case_id="PAST-01",
            canonical_name="HighRisk Vendor",
        ))
        recon_repo.create(ReconciliationRecordModel(
            reconciliation_id="REC-P1",
            case_id="PAST-01",
            status="CONTRADICTED",
            expected_amount=50000.0,
            explanation="Contradicted",
        ))
        txn_repo.create(TransactionRecord(
            id="TXN-P1",
            case_id="PAST-01",
            amount=50000.0,
            direction="CREDIT",
            bank_reference="UTR-RISKY-999",
        ))

        # Current case
        case_repo.create(CaseRecord(case_id="CURR-01", status="CONFIRMED"))
        ent_repo.create(EntityRecord(
            id="ENT-C1",
            case_id="CURR-01",
            canonical_name="HighRisk Vendor",
        ))
        txn_repo.create(TransactionRecord(
            id="TXN-C1",
            case_id="CURR-01",
            amount=50000.0,
            direction="CREDIT",
            bank_reference="UTR-RISKY-999",
        ))

    signals = service.get_historical_risk_signals("CURR-01")
    assert len(signals) >= 2

    sig_types = {s.signal_type for s in signals}
    assert "REPEAT_CONTRADICTION" in sig_types
    assert "REFERENCE_REUSE_DETECTED" in sig_types

    for s in signals:
        assert s.severity in ("CRITICAL", "WARNING", "INFO")
        assert "PAST-01" in s.affected_case_ids
        assert len(s.description) > 0
