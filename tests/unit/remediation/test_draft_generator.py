"""Unit tests for Fact-Grounded Notice Draft Generator (Day 19)."""

import pytest
from backend.case_processing.service import CaseProcessingService
from backend.controller.remediation.generator import RemediationDraftGenerator
from backend.controller.remediation.models import NoticeChannel, RemediationActionType
from backend.domain.reconciliation import ReconciliationStatus


@pytest.fixture
def sample_truth():
    case_service = CaseProcessingService()
    case_dict = {
        "case_id": "CASE-D19-T1",
        "evidence": [
            {
                "id": "EV-1",
                "modality": "INVOICE",
                "source_name": "inv.txt",
                "source_type": "MANUAL_UPLOAD",
                "raw_payload": "INVOICE #INV-101 Vendor: Apex Suppliers Amount: INR 60,000",
            },
            {
                "id": "EV-2",
                "modality": "BANK_STATEMENT",
                "source_name": "bank.csv",
                "source_type": "BANK_CSV",
                "raw_payload": "Credit 40000 UTR-APEX-01",
            }
        ],
        "claims": [
            {
                "id": "CLM-1",
                "evidence_id": "EV-1",
                "claim_type": "INVOICE_ISSUED",
                "claimed_amount": 60000.0,
                "reference_id_hint": "INV-101",
                "counterparty_hint": "Apex Suppliers",
            }
        ],
        "transactions": [
            {
                "id": "TXN-1",
                "amount": 40000.0,
                "direction": "CREDIT",
                "bank_reference": "UTR-APEX-01",
                "evidence_ids": ["EV-2"],
            }
        ],
        "entities": [{"id": "ENT-1", "canonical_name": "Apex Suppliers"}],
    }
    res = case_service.process_benchmark_case(case_dict)
    return res.reconciliation, res.report


def test_vendor_dispute_notice_generation(sample_truth):
    recon, report = sample_truth
    draft = RemediationDraftGenerator.generate_vendor_dispute_notice(
        case_id="CASE-D19-T1",
        recon=recon,
        report=report,
        channel=NoticeChannel.EMAIL,
        recipient_email_or_phone="accounts@apex.com",
    )
    assert draft.action_type == RemediationActionType.VENDOR_DISPUTE_NOTICE
    assert draft.recipient_name == "Apex Suppliers"
    assert draft.recipient_contact == "accounts@apex.com"
    assert "INV-101" in draft.cited_invoice_ids
    assert "UTR-APEX-01" in draft.cited_utr_references
    assert draft.stated_disputed_amount > 0
    assert "INR" in draft.body


def test_payment_followup_generation(sample_truth):
    recon, report = sample_truth
    draft = RemediationDraftGenerator.generate_payment_followup_draft(
        case_id="CASE-D19-T1",
        recon=recon,
        report=report,
    )
    assert draft.action_type == RemediationActionType.PAYMENT_FOLLOWUP_DRAFT
    assert draft.stated_disputed_amount > 0
    assert "INR" in draft.body


def test_missing_evidence_request_generation(sample_truth):
    recon, report = sample_truth
    draft = RemediationDraftGenerator.generate_missing_evidence_request(
        case_id="CASE-D19-T1",
        recon=recon,
        report=report,
    )
    assert draft.action_type == RemediationActionType.MISSING_EVIDENCE_REQUEST
    assert "Bank Statement" in draft.body
