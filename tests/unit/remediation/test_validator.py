"""Unit tests for Fact-Grounding and Journal Balance Validator (Day 19)."""

import pytest
from backend.controller.remediation.models import DraftJournalVoucher, JournalEntryLine, NoticeChannel, RemediationActionType, RemediationNoticeDraft
from backend.controller.remediation.validator import RemediationValidator
from backend.domain.reconciliation import ReconciliationStatus
from backend.reconciliation.result import ReconciliationResult
from backend.reporting.models import EntitySummary, FinancialTruthReport, ReportStatus


@pytest.fixture
def mock_recon():
    return ReconciliationResult(
        reconciliation_id="REC-VAL-1",
        status=ReconciliationStatus.CONFIRMED,
        expected_amount=50000.0,
        matched_amount=50000.0,
        outstanding_amount=0.0,
        explanation="Exact",
    )


def test_grounded_notice_validation_pass(mock_recon):
    draft = RemediationNoticeDraft(
        draft_id="D-1",
        action_type=RemediationActionType.PAYMENT_FOLLOWUP_DRAFT,
        channel=NoticeChannel.EMAIL,
        recipient_name="Valid Vendor",
        subject="Subject",
        body="Body",
        stated_expected_amount=50000.0,
        stated_matched_amount=50000.0,
        stated_disputed_amount=0.0,
    )
    is_valid, errors = RemediationValidator.validate_notice_grounding(draft, mock_recon)
    assert is_valid is True
    assert len(errors) == 0


def test_ungrounded_notice_validation_reject(mock_recon):
    draft = RemediationNoticeDraft(
        draft_id="D-2",
        action_type=RemediationActionType.VENDOR_DISPUTE_NOTICE,
        channel=NoticeChannel.EMAIL,
        recipient_name="Tampered Vendor",
        subject="Subject",
        body="Body",
        stated_expected_amount=999999.0,  # Fabricated / ungrounded figure
        stated_matched_amount=0.0,
        stated_disputed_amount=999999.0,
    )
    is_valid, errors = RemediationValidator.validate_notice_grounding(draft, mock_recon)
    assert is_valid is False
    assert len(errors) >= 1
    assert "Ungrounded" in errors[0]


def test_unbalanced_journal_validation_reject():
    lines = [
        JournalEntryLine(line_number=1, account_code="2100", account_name="AP", debit_amount=50000.0, credit_amount=0.0),
        JournalEntryLine(line_number=2, account_code="1100", account_name="Bank", debit_amount=0.0, credit_amount=40000.0),  # 10k imbalance
    ]
    voucher = DraftJournalVoucher(
        voucher_id="JV-UNBAL",
        case_id="CASE-1",
        is_draft=True,
        lines=lines,
        total_debits=50000.0,
        total_credits=40000.0,
        is_balanced=False,
        general_narration="Unbalanced test",
        provenance_hash="abc",
    )
    is_valid, errors = RemediationValidator.validate_journal_voucher(voucher)
    assert is_valid is False
    assert any("imbalance" in e.lower() for e in errors)
