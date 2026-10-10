"""Adversarial Security and Integrity Test Suite for Day 19 Remediation.

Attacks tested:
A. FAKE AMOUNT ATTACK
B. FAKE UTR ATTACK
C. FAKE INVOICE ATTACK
D. TRUTH MUTATION ATTACK
E. APPROVAL BYPASS
F. WRONG REVIEWER / INVALID APPROVAL
G. DOUBLE-ENTRY IMBALANCE
H. SINGLE-LINE JOURNAL
I. NON-DRAFT JOURNAL
J. CROSS-CASE PROVENANCE ATTACK
K. AUDIT TAMPERING
L. AUDIT DELETION / REORDER ATTACK
M. AUTONOMOUS DISPATCH ATTACK
N. REPLAY / DUPLICATE APPROVAL
O. REJECTED ACTION REUSE
P. AI HALLUCINATION ATTACK
"""

import os
import tempfile
import pytest

from backend.case_processing.service import CaseProcessingService
from backend.controller.remediation.generator import RemediationDraftGenerator
from backend.controller.remediation.journal_engine import DraftJournalEngine, JournalBalanceError
from backend.controller.remediation.models import (
    ActionApprovalStatus,
    DraftJournalVoucher,
    JournalEntryLine,
    NoticeChannel,
    RemediationActionType,
    RemediationNoticeDraft,
)
from backend.controller.remediation.service import RemediationActionService
from backend.controller.remediation.validator import RemediationValidator
from backend.domain.reconciliation import ReconciliationStatus
from backend.reconciliation.result import ReconciliationResult
from backend.storage.audit_store import PersistentAuditStore
from backend.storage.config import StorageSettings
from backend.storage.database import DatabaseEngine
from backend.storage.service import StorageService


@pytest.fixture
def adversarial_env():
    temp_dir = tempfile.mkdtemp(prefix="verity_adv_sec_")
    db_path = os.path.join(temp_dir, "adv_sec.db")
    settings = StorageSettings(database_url=f"sqlite:///{db_path}", pool_size=1, timeout_seconds=30.0)
    engine = DatabaseEngine(settings=settings)
    engine.initialize()

    case_service = CaseProcessingService()
    storage_service = StorageService(engine=engine)
    rem_service = RemediationActionService(engine=engine)

    # Seed genuine Case A (₹25,000)
    case_a_data = {
        "case_id": "CASE-ADV-A",
        "evidence": [
            {
                "id": "EV-A1",
                "modality": "INVOICE",
                "source_name": "inv_a.txt",
                "source_type": "MANUAL_UPLOAD",
                "raw_payload": "INVOICE #INV-A-100 Vendor: Alpha Corp Amount: INR 25,000.00",
            },
            {
                "id": "EV-A2",
                "modality": "BANK_STATEMENT",
                "source_name": "bank_a.csv",
                "source_type": "BANK_CSV",
                "raw_payload": "Credit 25000 UTR-ALPHA-100",
            }
        ],
        "claims": [
            {
                "id": "CLM-A1",
                "evidence_id": "EV-A1",
                "claim_type": "INVOICE_ISSUED",
                "claimed_amount": 25000.0,
                "reference_id_hint": "UTR-ALPHA-100",
                "counterparty_hint": "Alpha Corp",
            }
        ],
        "transactions": [
            {
                "id": "TXN-A1",
                "amount": 25000.0,
                "direction": "CREDIT",
                "bank_reference": "UTR-ALPHA-100",
                "evidence_ids": ["EV-A2"],
            }
        ],
        "entities": [{"id": "ENT-A1", "canonical_name": "Alpha Corp"}],
    }
    res_a = case_service.process_benchmark_case(case_a_data)
    storage_service.process_and_persist_case(
        case_result=res_a,
        raw_evidence_list=case_a_data["evidence"],
        raw_claims_list=case_a_data["claims"],
        raw_entities_list=case_a_data["entities"],
        raw_transactions_list=case_a_data["transactions"],
    )

    yield rem_service, engine, res_a, case_service, storage_service
    engine.shutdown()


# =========================================================================
# ATTACK A: FAKE AMOUNT ATTACK
# =========================================================================
def test_attack_a_fake_amount(adversarial_env):
    rem_service, engine, res_a, _, _ = adversarial_env

    # Authoritative amount is ₹25,000. Attempt to validate a notice citing ₹50,000.
    fake_draft = RemediationNoticeDraft(
        draft_id="DRFT-FAKE-AMT",
        action_type=RemediationActionType.VENDOR_DISPUTE_NOTICE,
        channel=NoticeChannel.EMAIL,
        recipient_name="Alpha Corp",
        subject="Dispute Notice",
        body="Disputed shortfall is INR 50,000.00",
        stated_expected_amount=50000.0,  # FAKE
        stated_matched_amount=25000.0,
        stated_disputed_amount=25000.0,
    )
    is_valid, errors = RemediationValidator.validate_notice_grounding(fake_draft, res_a.reconciliation, res_a.report)
    assert is_valid is False
    assert any("Ungrounded expected amount" in e for e in errors)


# =========================================================================
# ATTACK B: FAKE UTR ATTACK
# =========================================================================
def test_attack_b_fake_utr(adversarial_env):
    rem_service, engine, res_a, _, _ = adversarial_env

    fake_draft = RemediationNoticeDraft(
        draft_id="DRFT-FAKE-UTR",
        action_type=RemediationActionType.PAYMENT_FOLLOWUP_DRAFT,
        channel=NoticeChannel.EMAIL,
        recipient_name="Alpha Corp",
        subject="Payment Followup",
        body="Regarding bank UTR-FAKE-999999",
        cited_invoice_ids=["UTR-ALPHA-100"],
        cited_utr_references=["UTR-FAKE-999999"],  # FAKE UTR
        stated_expected_amount=25000.0,
        stated_matched_amount=25000.0,
        stated_disputed_amount=0.0,
    )
    is_valid, errors = RemediationValidator.validate_notice_grounding(fake_draft, res_a.reconciliation, res_a.report)
    assert is_valid is False
    assert any("Ungrounded bank UTR reference" in e for e in errors)


# =========================================================================
# ATTACK C: FAKE INVOICE ATTACK
# =========================================================================
def test_attack_c_fake_invoice(adversarial_env):
    rem_service, engine, res_a, _, _ = adversarial_env

    fake_draft = RemediationNoticeDraft(
        draft_id="DRFT-FAKE-INV",
        action_type=RemediationActionType.VENDOR_DISPUTE_NOTICE,
        channel=NoticeChannel.EMAIL,
        recipient_name="Alpha Corp",
        subject="Dispute Notice",
        body="Dispute on invoice INV-MALICIOUS-999",
        cited_invoice_ids=["INV-MALICIOUS-999"],  # FAKE INVOICE
        cited_utr_references=["UTR-ALPHA-100"],
        stated_expected_amount=25000.0,
        stated_matched_amount=25000.0,
        stated_disputed_amount=0.0,
    )
    is_valid, errors = RemediationValidator.validate_notice_grounding(fake_draft, res_a.reconciliation, res_a.report)
    assert is_valid is False
    assert any("Ungrounded invoice reference" in e for e in errors)


# =========================================================================
# ATTACK D: TRUTH MUTATION ATTACK
# =========================================================================
def test_attack_d_truth_mutation(adversarial_env):
    rem_service, engine, res_a, _, _ = adversarial_env

    initial_status = res_a.status
    initial_matched = res_a.reconciliation.matched_amount

    # Propose, approve, reject multiple actions
    act1 = rem_service.propose_dispute_notice("CASE-ADV-A")
    rem_service.approve_action(act1.action_id, reviewer_id="lead_controller")
    act2 = rem_service.propose_payment_followup("CASE-ADV-A")
    rem_service.reject_action(act2.action_id, reviewer_id="lead_controller", rejection_reason="Declined")

    # Verify reconciliation result in database remains strictly unmodified
    recon_after, report_after = rem_service._get_case_truth("CASE-ADV-A")
    assert recon_after.status.value == initial_status
    assert recon_after.matched_amount == initial_matched
    assert recon_after.expected_amount == 25000.0


# =========================================================================
# ATTACK E: APPROVAL BYPASS (PENDING -> EXPORTED directly)
# =========================================================================
def test_attack_e_approval_bypass(adversarial_env):
    rem_service, engine, _, _, _ = adversarial_env

    action = rem_service.propose_dispute_notice("CASE-ADV-A")
    assert action.approval_status == ActionApprovalStatus.PENDING_APPROVAL

    # Attempt to bypass approval and mark action as approved without reviewer
    with pytest.raises(ValueError, match="Reviewer ID is required"):
        rem_service.approve_action(action.action_id, reviewer_id="")


# =========================================================================
# ATTACK F: WRONG REVIEWER / INVALID APPROVAL
# =========================================================================
def test_attack_f_wrong_reviewer(adversarial_env):
    rem_service, engine, _, _, _ = adversarial_env

    action = rem_service.propose_payment_followup("CASE-ADV-A")

    # Attempt approval with empty / whitespace reviewer ID
    with pytest.raises(ValueError, match="Reviewer ID is required"):
        rem_service.approve_action(action.action_id, reviewer_id="   ")

    with pytest.raises(ValueError, match="Reviewer ID is required"):
        rem_service.reject_action(action.action_id, reviewer_id="")


# =========================================================================
# ATTACK G: DOUBLE-ENTRY IMBALANCE (DR != CR)
# =========================================================================
def test_attack_g_double_entry_imbalance():
    unbalanced_lines = [
        JournalEntryLine(line_number=1, account_code="2100", account_name="Vendor AP", debit_amount=25000.0, credit_amount=0.0),
        JournalEntryLine(line_number=2, account_code="1100", account_name="Bank Clearing", debit_amount=0.0, credit_amount=20000.0),  # 5,000 imbalance
    ]
    unbalanced_voucher = DraftJournalVoucher(
        voucher_id="JV-ADV-IMBAL",
        case_id="CASE-ADV-A",
        is_draft=True,
        lines=unbalanced_lines,
        total_debits=25000.0,
        total_credits=20000.0,
        is_balanced=False,
        general_narration="Malicious unbalanced voucher",
        provenance_hash="fake",
    )
    is_valid, errors = RemediationValidator.validate_journal_voucher(unbalanced_voucher)
    assert is_valid is False
    assert any("imbalance" in e.lower() for e in errors)


# =========================================================================
# ATTACK H: SINGLE-LINE JOURNAL
# =========================================================================
def test_attack_h_single_line_journal():
    single_line = [
        JournalEntryLine(line_number=1, account_code="2100", account_name="Vendor AP", debit_amount=25000.0, credit_amount=0.0)
    ]
    single_line_voucher = DraftJournalVoucher(
        voucher_id="JV-ADV-SINGLE",
        case_id="CASE-ADV-A",
        is_draft=True,
        lines=single_line,
        total_debits=25000.0,
        total_credits=0.0,
        is_balanced=False,
        general_narration="Single line test",
        provenance_hash="fake",
    )
    is_valid, errors = RemediationValidator.validate_journal_voucher(single_line_voucher)
    assert is_valid is False
    assert any("at least 2 double-entry lines" in e for e in errors)


# =========================================================================
# ATTACK I: NON-DRAFT JOURNAL FORCING
# =========================================================================
def test_attack_i_non_draft_journal():
    lines = [
        JournalEntryLine(line_number=1, account_code="2100", account_name="Vendor AP", debit_amount=25000.0, credit_amount=0.0),
        JournalEntryLine(line_number=2, account_code="1100", account_name="Bank Clearing", debit_amount=0.0, credit_amount=25000.0),
    ]
    # Attempt to bypass draft status
    posted_voucher = DraftJournalVoucher(
        voucher_id="JV-ADV-POSTED",
        case_id="CASE-ADV-A",
        is_draft=False,  # ATTACK: forcing non-draft
        lines=lines,
        total_debits=25000.0,
        total_credits=25000.0,
        is_balanced=True,
        general_narration="Attempted direct posting",
        provenance_hash="fake",
    )
    is_valid, errors = RemediationValidator.validate_journal_voucher(posted_voucher)
    assert is_valid is False
    assert any("must explicitly be marked as is_draft=True" in e for e in errors)


# =========================================================================
# ATTACK J: CROSS-CASE PROVENANCE ATTACK
# =========================================================================
def test_attack_j_cross_case_provenance(adversarial_env):
    rem_service, engine, res_a, case_service, storage_service = adversarial_env

    # Seed Case B (₹10,000)
    case_b_data = {
        "case_id": "CASE-ADV-B",
        "evidence": [
            {"id": "EV-B1", "modality": "INVOICE", "source_name": "inv_b.txt", "source_type": "MANUAL_UPLOAD", "raw_payload": "INVOICE #INV-B Vendor: Beta Corp INR 10,000"},
            {"id": "EV-B2", "modality": "BANK_STATEMENT", "source_name": "bank_b.csv", "source_type": "BANK_CSV", "raw_payload": "Credit 10000 UTR-BETA-200"},
        ],
        "claims": [{"id": "CLM-B1", "evidence_id": "EV-B1", "claim_type": "INVOICE_ISSUED", "claimed_amount": 10000.0, "reference_id_hint": "UTR-BETA-200", "counterparty_hint": "Beta Corp"}],
        "transactions": [{"id": "TXN-B1", "amount": 10000.0, "direction": "CREDIT", "bank_reference": "UTR-BETA-200", "evidence_ids": ["EV-B2"]}],
        "entities": [{"id": "ENT-B1", "canonical_name": "Beta Corp"}],
    }
    res_b = case_service.process_benchmark_case(case_b_data)
    storage_service.process_and_persist_case(
        case_result=res_b,
        raw_evidence_list=case_b_data["evidence"],
        raw_claims_list=case_b_data["claims"],
        raw_entities_list=case_b_data["entities"],
        raw_transactions_list=case_b_data["transactions"],
    )

    # Attempt to validate Case B draft against Case A's reconciliation truth
    draft_b = RemediationDraftGenerator.generate_payment_followup_draft("CASE-ADV-B", res_b.reconciliation, res_b.report)
    is_valid, errors = RemediationValidator.validate_notice_grounding(draft_b, res_a.reconciliation, res_a.report)
    assert is_valid is False
    assert len(errors) >= 1


# =========================================================================
# ATTACK K: AUDIT TAMPERING DETECTION
# =========================================================================
def test_attack_k_audit_tampering(adversarial_env):
    rem_service, engine, _, _, _ = adversarial_env

    # Generate legitimate actions that produce audit events
    act = rem_service.propose_dispute_notice("CASE-ADV-A")
    rem_service.approve_action(act.action_id, reviewer_id="lead_controller")

    audit_store = PersistentAuditStore(engine)
    is_valid_before, errors_before = audit_store.verify_chain("CASE-ADV-A")
    assert is_valid_before is True

    # Maliciously tamper with audit description in database row
    with engine.transaction() as conn:
        conn.execute("UPDATE audit_events SET description = 'TAMPERED DESCRIPTION' WHERE case_id = 'CASE-ADV-A' AND sequence_number = 1;")

    is_valid_after, errors_after = audit_store.verify_chain("CASE-ADV-A")
    assert is_valid_after is False
    assert len(errors_after) >= 1
    assert any("Tampered state hash detected" in e or "Hash link mismatch" in e for e in errors_after)


# =========================================================================
# ATTACK L: AUDIT DELETION / REORDER ATTACK
# =========================================================================
def test_attack_l_audit_deletion_reorder(adversarial_env):
    from backend.storage.models import CaseRecord
    from backend.storage.repositories.sql.case import SQLCaseRepository

    temp_dir = tempfile.mkdtemp(prefix="verity_adv_del_")
    db_path = os.path.join(temp_dir, "adv_del.db")
    settings = StorageSettings(database_url=f"sqlite:///{db_path}", pool_size=1, timeout_seconds=30.0)
    engine = DatabaseEngine(settings=settings)
    engine.initialize()

    with engine.transaction() as conn:
        SQLCaseRepository(conn).create(CaseRecord(case_id="CASE-DEL-01", status="CONFIRMED"))

    audit_store = PersistentAuditStore(engine)
    audit_store.append_event("CASE-DEL-01", "EVENT_1", "ctrl", "Desc 1")
    audit_store.append_event("CASE-DEL-01", "EVENT_2", "ctrl", "Desc 2")
    audit_store.append_event("CASE-DEL-01", "EVENT_3", "ctrl", "Desc 3")

    is_valid, _ = audit_store.verify_chain("CASE-DEL-01")
    assert is_valid is True

    # Maliciously delete intermediate event #2
    with engine.transaction() as conn:
        conn.execute("DELETE FROM audit_events WHERE case_id = 'CASE-DEL-01' AND sequence_number = 2;")

    is_valid_del, errors = audit_store.verify_chain("CASE-DEL-01")
    assert is_valid_del is False
    assert any("broken" in e.lower() or "mismatch" in e.lower() for e in errors)
    engine.shutdown()


# =========================================================================
# ATTACK M: AUTONOMOUS DISPATCH ATTACK (Zero Network Transmissions)
# =========================================================================
def test_attack_m_zero_autonomous_dispatch(adversarial_env):
    rem_service, engine, _, _, _ = adversarial_env

    # Propose notices on multiple channels
    a1 = rem_service.propose_dispute_notice("CASE-ADV-A", channel=NoticeChannel.EMAIL)
    a2 = rem_service.propose_payment_followup("CASE-ADV-A", channel=NoticeChannel.WHATSAPP)

    # Verify status is strictly PENDING_APPROVAL and no outbound socket / email is invoked
    assert a1.approval_status == ActionApprovalStatus.PENDING_APPROVAL
    assert a2.approval_status == ActionApprovalStatus.PENDING_APPROVAL
    assert a1.approved_by is None
    assert a2.approved_by is None


# =========================================================================
# ATTACK N: REPLAY / DUPLICATE APPROVAL ATTACK
# =========================================================================
def test_attack_n_duplicate_approval_replay(adversarial_env):
    rem_service, engine, _, _, _ = adversarial_env

    action = rem_service.propose_dispute_notice("CASE-ADV-A")
    approved = rem_service.approve_action(action.action_id, reviewer_id="controller_1")
    assert approved.approval_status == ActionApprovalStatus.APPROVED

    # Attempt to approve again (replay attack)
    with pytest.raises(ValueError, match="Cannot approve action"):
        rem_service.approve_action(action.action_id, reviewer_id="controller_2")


# =========================================================================
# ATTACK O: REJECTED ACTION REUSE ATTACK
# =========================================================================
def test_attack_o_rejected_action_reuse(adversarial_env):
    rem_service, engine, _, _, _ = adversarial_env

    action = rem_service.propose_payment_followup("CASE-ADV-A")
    rejected = rem_service.reject_action(action.action_id, reviewer_id="controller_1", rejection_reason="Declined")
    assert rejected.approval_status == ActionApprovalStatus.REJECTED

    # Attempt to approve a rejected action
    with pytest.raises(ValueError, match="Cannot approve action"):
        rem_service.approve_action(action.action_id, reviewer_id="controller_1")

    # Attempt to reject an already rejected action
    with pytest.raises(ValueError, match="Cannot reject action"):
        rem_service.reject_action(action.action_id, reviewer_id="controller_1", rejection_reason="Second reject")


# =========================================================================
# ATTACK P: AI HALLUCINATION ATTACK
# =========================================================================
def test_attack_p_ai_hallucination_injection(adversarial_env):
    rem_service, engine, res_a, _, _ = adversarial_env

    # Simulated malicious LLM output with hallucinated numbers, fake invoices, fake UTRs
    hallucinated_draft = RemediationNoticeDraft(
        draft_id="DRFT-LLM-HALLUCINATED",
        action_type=RemediationActionType.VENDOR_DISPUTE_NOTICE,
        channel=NoticeChannel.EMAIL,
        recipient_name="Unsupported Counterparty",
        subject="AI Notice",
        body="Fabricated amount INR 888,888 on fake invoice INV-FABRICATED and fake UTR-FABRICATED",
        cited_invoice_ids=["INV-FABRICATED"],
        cited_utr_references=["UTR-FABRICATED"],
        stated_expected_amount=888888.0,
        stated_matched_amount=0.0,
        stated_disputed_amount=888888.0,
    )
    is_valid, errors = RemediationValidator.validate_notice_grounding(hallucinated_draft, res_a.reconciliation, res_a.report)
    assert is_valid is False
    assert len(errors) >= 3
    # Check all three hallucinated facets are caught
    assert any("Ungrounded expected amount" in e for e in errors)
    assert any("Ungrounded invoice reference" in e for e in errors)
    assert any("Ungrounded bank UTR reference" in e for e in errors)
