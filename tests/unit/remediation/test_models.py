"""Unit tests for Remediation domain models (Day 19)."""

import pytest
from backend.controller.remediation.models import (
    ActionApprovalStatus,
    DraftJournalVoucher,
    JournalEntryLine,
    NoticeChannel,
    RemediationAction,
    RemediationActionType,
    RemediationNoticeDraft,
)


def test_remediation_notice_draft_model():
    draft = RemediationNoticeDraft(
        draft_id="DRFT-001",
        action_type=RemediationActionType.VENDOR_DISPUTE_NOTICE,
        channel=NoticeChannel.EMAIL,
        recipient_name="Acme Corp",
        subject="Dispute Notice",
        body="Discrepancy identified regarding Invoice #101",
        cited_invoice_ids=["INV-101"],
        cited_utr_references=["UTR123456"],
        stated_expected_amount=50000.0,
        stated_matched_amount=30000.0,
        stated_disputed_amount=20000.0,
        grounding_verified=True,
    )
    assert draft.draft_id == "DRFT-001"
    assert draft.stated_disputed_amount == 20000.0
    assert draft.grounding_verified is True


def test_draft_journal_voucher_model():
    lines = [
        JournalEntryLine(line_number=1, account_code="2100", account_name="Vendor AP", debit_amount=50000.0, credit_amount=0.0),
        JournalEntryLine(line_number=2, account_code="1100", account_name="Bank Clearing", debit_amount=0.0, credit_amount=50000.0),
    ]
    voucher = DraftJournalVoucher(
        voucher_id="JV-001",
        case_id="CASE-1",
        is_draft=True,
        requires_account_mapping=True,
        lines=lines,
        total_debits=50000.0,
        total_credits=50000.0,
        is_balanced=True,
        general_narration="Settlement for Acme Corp",
        provenance_hash="abcdef",
    )
    assert voucher.voucher_id == "JV-001"
    assert voucher.is_draft is True
    assert voucher.requires_account_mapping is True
    assert voucher.is_balanced is True


def test_remediation_action_lifecycle_model():
    action = RemediationAction(
        action_id="ACT-001",
        case_id="CASE-100",
        action_type=RemediationActionType.VENDOR_DISPUTE_NOTICE,
        approval_status=ActionApprovalStatus.PENDING_APPROVAL,
        title="Dispute Notice for Acme Corp",
        summary="Shortfall of INR 20,000",
    )
    assert action.approval_status == ActionApprovalStatus.PENDING_APPROVAL
    assert action.approved_by is None
