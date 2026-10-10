"""Unit tests for SQL Repositories."""

import pytest
from backend.storage.config import StorageSettings
from backend.storage.database import DatabaseEngine
from backend.storage.models import (
    CaseAssignmentRecord,
    CaseRecord,
    ClaimRecord,
    DiscrepancyRecord,
    EntityRecord,
    EvidenceRecord,
    EvidenceReviewRecordModel,
    IdempotencyRecord,
    MatchRelationshipRecord,
    PortfolioStateRecord,
    ReconciliationRecordModel,
    ReviewNoteRecord,
    ReviewRecordModel,
    TransactionRecord,
    TruthReportRecord,
)
from backend.storage.repositories.sql import (
    SQLCaseRepository,
    SQLClaimRepository,
    SQLDiscrepancyRepository,
    SQLEntityRepository,
    SQLEvidenceRepository,
    SQLIdempotencyRepository,
    SQLMatchRepository,
    SQLPortfolioRepository,
    SQLReconciliationRepository,
    SQLReviewRepository,
    SQLTransactionRepository,
    SQLTruthReportRepository,
)


@pytest.fixture
def db_conn():
    settings = StorageSettings(database_url="sqlite:///:memory:")
    engine = DatabaseEngine(settings)
    engine.initialize()
    with engine.get_connection() as conn:
        yield conn
    engine.shutdown()


def test_case_repository_crud(db_conn):
    repo = SQLCaseRepository(db_conn)
    rec = CaseRecord(case_id="CASE-01", status="CONFIRMED", confidence_score=0.98)
    repo.create(rec)

    fetched = repo.get("CASE-01")
    assert fetched is not None
    assert fetched.case_id == "CASE-01"
    assert fetched.confidence_score == 0.98

    all_cases = repo.list_all()
    assert len(all_cases) == 1

    deleted = repo.delete_if_allowed("CASE-01")
    assert deleted is True
    assert repo.get("CASE-01") is None


def test_evidence_and_claims_repository(db_conn):
    case_repo = SQLCaseRepository(db_conn)
    case_repo.create(CaseRecord(case_id="CASE-02", status="CONFIRMED"))

    ev_repo = SQLEvidenceRepository(db_conn)
    ev_rec = EvidenceRecord(
        id="EV-1",
        case_id="CASE-02",
        modality="INVOICE",
        sha256_hash="a" * 64,
        source_name="inv.pdf",
    )
    ev_repo.create(ev_rec)

    # Immutability duplicate ignore
    ev_repo.create(ev_rec)
    ev_list = ev_repo.list_by_case("CASE-02")
    assert len(ev_list) == 1

    claim_repo = SQLClaimRepository(db_conn)
    claim_rec = ClaimRecord(
        id="CLM-1",
        case_id="CASE-02",
        evidence_id="EV-1",
        claim_type="INVOICE_ISSUED",
        claimed_amount=1000.0,
    )
    claim_repo.create(claim_rec)
    clm_list = claim_repo.list_by_case("CASE-02")
    assert len(clm_list) == 1
    assert clm_list[0].claimed_amount == 1000.0


def test_reconciliation_repository(db_conn):
    case_repo = SQLCaseRepository(db_conn)
    case_repo.create(CaseRecord(case_id="CASE-03", status="CONFIRMED"))

    recon_repo = SQLReconciliationRepository(db_conn)
    recon_rec = ReconciliationRecordModel(
        reconciliation_id="REC-03",
        case_id="CASE-03",
        status="CONFIRMED",
        expected_amount=5000.0,
        matched_amount=5000.0,
        outstanding_amount=0.0,
        currency="INR",
        confidence_score=0.99,
        explanation="Full settlement confirmed",
    )
    recon_repo.create(recon_rec)

    loaded = recon_repo.get_by_case("CASE-03")
    assert loaded is not None
    assert loaded.reconciliation_id == "REC-03"
    assert loaded.expected_amount == 5000.0
    assert loaded.status == "CONFIRMED"


def test_review_and_notes_repository(db_conn):
    case_repo = SQLCaseRepository(db_conn)
    case_repo.create(CaseRecord(case_id="CASE-04", status="CONTRADICTED"))

    rev_repo = SQLReviewRepository(db_conn)
    rev_rec = ReviewRecordModel(
        review_id="REV-04",
        case_id="CASE-04",
        status="IN_REVIEW",
        decision=None,
        assigned_to="ctrl_sarah",
    )
    rev_repo.create(rev_rec)

    note = ReviewNoteRecord(
        note_id="N-1",
        case_id="CASE-04",
        review_id="REV-04",
        author_id="ctrl_sarah",
        author_name="Sarah",
        note_type="OBSERVATION",
        content="Testing review note",
    )
    rev_repo.add_note(note)

    notes = rev_repo.list_notes("CASE-04")
    assert len(notes) == 1
    assert notes[0].content == "Testing review note"


def test_portfolio_repository(db_conn):
    case_repo = SQLCaseRepository(db_conn)
    case_repo.create(CaseRecord(case_id="CASE-05", status="CONFIRMED"))

    port_repo = SQLPortfolioRepository(db_conn)
    state = PortfolioStateRecord(
        case_id="CASE-05",
        portfolio_status="ASSIGNED",
        priority="HIGH",
        priority_score=8.5,
        amount_exposure=15000.0,
    )
    port_repo.save_state(state)

    asg = CaseAssignmentRecord(
        case_id="CASE-05",
        reviewer_id="ctrl_bob",
        reviewer_name="Bob",
        active=True,
    )
    port_repo.save_assignment(asg)

    loaded_state = port_repo.get_state("CASE-05")
    loaded_asg = port_repo.get_assignment("CASE-05")
    assert loaded_state.priority == "HIGH"
    assert loaded_asg.reviewer_id == "ctrl_bob"


def test_idempotency_repository(db_conn):
    repo = SQLIdempotencyRepository(db_conn)
    rec = IdempotencyRecord(
        key="KEY-01",
        case_id="CASE-06",
        request_hash="hash123",
        response_reference="REF-01",
    )
    repo.create(rec)

    fetched = repo.get("KEY-01")
    assert fetched is not None
    assert fetched.request_hash == "hash123"
    assert fetched.response_reference == "REF-01"
