"""Unit tests for Reference / UTR Reuse Detection (Day 18)."""

import os
import tempfile
import pytest

from backend.cross_case.service import CrossCaseIntelligenceService
from backend.storage.config import StorageSettings
from backend.storage.database import DatabaseEngine
from backend.storage.models import (
    ClaimRecord,
    TransactionRecord,
)
from backend.storage.repositories.sql.claim import SQLClaimRepository
from backend.storage.repositories.sql.transaction import SQLTransactionRepository


@pytest.fixture
def test_engine():
    temp_dir = tempfile.mkdtemp(prefix="verity_test_ref_")
    db_path = os.path.join(temp_dir, "test_ref.db")
    settings = StorageSettings(database_url=f"sqlite:///{db_path}", pool_size=3)
    engine = DatabaseEngine(settings=settings)
    engine.initialize()
    yield engine
    engine.shutdown()


def test_reference_reuse_detected(test_engine):
    service = CrossCaseIntelligenceService(engine=test_engine)

    with test_engine.transaction() as conn:
        from backend.storage.models import CaseRecord
        from backend.storage.repositories.sql.case import SQLCaseRepository
        case_repo = SQLCaseRepository(conn)
        case_repo.create(CaseRecord(case_id="CASE-2026-001", status="CONFIRMED"))
        case_repo.create(CaseRecord(case_id="CASE-2026-002", status="CONFIRMED"))

        txn_repo = SQLTransactionRepository(conn)
        claim_repo = SQLClaimRepository(conn)

        # Case 1 has transaction with UTR 408219381920
        txn_repo.create(TransactionRecord(
            id="TXN-101",
            case_id="CASE-2026-001",
            amount=50000.0,
            direction="CREDIT",
            bank_reference="408219381920",
        ))

        # Case 2 claims the exact same UTR
        claim_repo.create(ClaimRecord(
            id="CLM-201",
            case_id="CASE-2026-002",
            evidence_id="EV-1",
            claim_type="INVOICE_ISSUED",
            claimed_amount=50000.0,
            reference_id_hint="408219381920",
        ))

    # Query from perspective of CASE-2026-002
    ref_corr = service.get_reference_history("408219381920", current_case_id="CASE-2026-002")
    assert ref_corr.reference_id == "408219381920"
    assert ref_corr.occurrence_count == 2
    assert ref_corr.reuse_warning is True
    assert "CASE-2026-001" in ref_corr.previous_case_ids
    assert "TXN-101" in ref_corr.transaction_ids
    assert "CLM-201" in ref_corr.claim_ids


def test_unique_reference_no_warning(test_engine):
    service = CrossCaseIntelligenceService(engine=test_engine)

    with test_engine.transaction() as conn:
        from backend.storage.models import CaseRecord
        from backend.storage.repositories.sql.case import SQLCaseRepository
        case_repo = SQLCaseRepository(conn)
        case_repo.create(CaseRecord(case_id="CASE-2026-003", status="CONFIRMED"))

        txn_repo = SQLTransactionRepository(conn)
        txn_repo.create(TransactionRecord(
            id="TXN-301",
            case_id="CASE-2026-003",
            amount=12000.0,
            direction="CREDIT",
            bank_reference="UTR-UNIQUE-999",
        ))

    ref_corr = service.get_reference_history("UTR-UNIQUE-999", current_case_id="CASE-2026-003")
    assert ref_corr.reuse_warning is False
    assert ref_corr.occurrence_count == 1
