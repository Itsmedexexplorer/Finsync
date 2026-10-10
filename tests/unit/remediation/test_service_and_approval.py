"""Unit tests for RemediationActionService approval workflow and audit chain integration (Day 19)."""

import os
import tempfile
import pytest

from backend.case_processing.service import CaseProcessingService
from backend.controller.remediation.models import ActionApprovalStatus, RemediationActionType
from backend.controller.remediation.service import RemediationActionService
from backend.storage.config import StorageSettings
from backend.storage.database import DatabaseEngine
from backend.storage.service import StorageService


@pytest.fixture
def remediation_env():
    temp_dir = tempfile.mkdtemp(prefix="verity_test_rem_")
    db_path = os.path.join(temp_dir, "test_rem.db")
    settings = StorageSettings(database_url=f"sqlite:///{db_path}", pool_size=1, timeout_seconds=30.0)
    engine = DatabaseEngine(settings=settings)
    engine.initialize()

    case_service = CaseProcessingService()
    storage_service = StorageService(engine=engine)
    rem_service = RemediationActionService(engine=engine)

    # Seed a case
    case_data = {
        "case_id": "CASE-REM-001",
        "evidence": [
            {
                "id": "EV-1",
                "modality": "INVOICE",
                "source_name": "inv.txt",
                "source_type": "MANUAL_UPLOAD",
                "raw_payload": "INVOICE #INV-999 Vendor: Delta Logistics Amount: INR 40,000",
            },
            {
                "id": "EV-2",
                "modality": "BANK_STATEMENT",
                "source_name": "bank.csv",
                "source_type": "BANK_CSV",
                "raw_payload": "Credit 40000 UTR-DELTA-999",
            }
        ],
        "claims": [
            {
                "id": "CLM-1",
                "evidence_id": "EV-1",
                "claim_type": "INVOICE_ISSUED",
                "claimed_amount": 40000.0,
                "reference_id_hint": "UTR-DELTA-999",
                "counterparty_hint": "Delta Logistics",
            }
        ],
        "transactions": [
            {
                "id": "TXN-1",
                "amount": 40000.0,
                "direction": "CREDIT",
                "bank_reference": "UTR-DELTA-999",
                "evidence_ids": ["EV-2"],
            }
        ],
        "entities": [{"id": "ENT-1", "canonical_name": "Delta Logistics"}],
    }
    res = case_service.process_benchmark_case(case_data)
    storage_service.process_and_persist_case(
        case_result=res,
        raw_evidence_list=case_data["evidence"],
        raw_claims_list=case_data["claims"],
        raw_entities_list=case_data["entities"],
        raw_transactions_list=case_data["transactions"],
    )

    yield rem_service, engine
    engine.shutdown()


def test_action_proposal_and_approval_workflow(remediation_env):
    rem_service, engine = remediation_env

    # 1. Propose action
    action = rem_service.propose_payment_followup("CASE-REM-001")
    assert action.action_id.startswith("ACT-FLW-")
    assert action.approval_status == ActionApprovalStatus.PENDING_APPROVAL
    assert action.approved_by is None

    # 2. Approve action
    approved = rem_service.approve_action(action.action_id, reviewer_id="lead_controller_99")
    assert approved.approval_status == ActionApprovalStatus.APPROVED
    assert approved.approved_by == "lead_controller_99"
    assert approved.approved_at is not None


def test_action_rejection_workflow(remediation_env):
    rem_service, engine = remediation_env

    # 1. Propose action
    action = rem_service.propose_missing_evidence_request("CASE-REM-001")
    assert action.approval_status == ActionApprovalStatus.PENDING_APPROVAL

    # 2. Reject action
    rejected = rem_service.reject_action(
        action.action_id,
        reviewer_id="lead_controller_99",
        rejection_reason="Duplicate request avoided",
    )
    assert rejected.approval_status == ActionApprovalStatus.REJECTED
    assert rejected.rejection_reason == "Duplicate request avoided"


def test_draft_journal_voucher_proposal(remediation_env):
    rem_service, engine = remediation_env

    action = rem_service.propose_journal_voucher_action("CASE-REM-001")
    assert action.action_type == RemediationActionType.DRAFT_JOURNAL_VOUCHER
    assert action.journal_voucher is not None
    assert action.journal_voucher.is_balanced is True
    assert action.journal_voucher.total_debits == 40000.0
    assert action.journal_voucher.total_credits == 40000.0
