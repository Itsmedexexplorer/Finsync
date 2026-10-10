"""Unit tests for Double-Entry Draft Journal Engine (Day 19)."""

import pytest
from backend.case_processing.service import CaseProcessingService
from backend.controller.remediation.journal_engine import DraftJournalEngine, JournalBalanceError
from backend.domain.reconciliation import ReconciliationStatus


@pytest.fixture
def clean_case():
    case_service = CaseProcessingService()
    case_dict = {
        "case_id": "CASE-CLN",
        "evidence": [
            {
                "id": "EV-1",
                "modality": "INVOICE",
                "source_name": "inv.txt",
                "source_type": "MANUAL_UPLOAD",
                "raw_payload": "INVOICE #INV-CLN Vendor: Clean Vendor Ltd Amount: INR 50,000",
            },
            {
                "id": "EV-2",
                "modality": "BANK_STATEMENT",
                "source_name": "bank.csv",
                "source_type": "BANK_CSV",
                "raw_payload": "Credit 50000 UTR-CLN-999",
            }
        ],
        "claims": [
            {
                "id": "CLM-1",
                "evidence_id": "EV-1",
                "claim_type": "INVOICE_ISSUED",
                "claimed_amount": 50000.0,
                "reference_id_hint": "UTR-CLN-999",
                "counterparty_hint": "Clean Vendor Ltd",
            }
        ],
        "transactions": [
            {
                "id": "TXN-1",
                "amount": 50000.0,
                "direction": "CREDIT",
                "bank_reference": "UTR-CLN-999",
                "evidence_ids": ["EV-2"],
            }
        ],
        "entities": [{"id": "ENT-1", "canonical_name": "Clean Vendor Ltd"}],
    }
    res = case_service.process_benchmark_case(case_dict)
    return res.reconciliation, res.report


@pytest.fixture
def partial_case():
    case_service = CaseProcessingService()
    case_dict = {
        "case_id": "CASE-PRT",
        "evidence": [
            {
                "id": "EV-1",
                "modality": "INVOICE",
                "source_name": "inv.txt",
                "source_type": "MANUAL_UPLOAD",
                "raw_payload": "INVOICE #INV-PRT Vendor: Partial Vendor Amount: INR 50,000",
            },
            {
                "id": "EV-2",
                "modality": "BANK_STATEMENT",
                "source_name": "bank.csv",
                "source_type": "BANK_CSV",
                "raw_payload": "Credit 30000 UTR-PRT-111",
            }
        ],
        "claims": [
            {
                "id": "CLM-1",
                "evidence_id": "EV-1",
                "claim_type": "INVOICE_ISSUED",
                "claimed_amount": 50000.0,
                "reference_id_hint": "UTR-PRT-111",
                "counterparty_hint": "Partial Vendor",
            }
        ],
        "transactions": [
            {
                "id": "TXN-1",
                "amount": 30000.0,
                "direction": "CREDIT",
                "bank_reference": "UTR-PRT-111",
                "evidence_ids": ["EV-2"],
            }
        ],
        "entities": [{"id": "ENT-1", "canonical_name": "Partial Vendor"}],
    }
    res = case_service.process_benchmark_case(case_dict)
    return res.reconciliation, res.report


def test_confirmed_case_generates_balanced_voucher(clean_case):
    recon, report = clean_case
    voucher = DraftJournalEngine.generate_draft_voucher(
        case_id="CASE-CLN",
        recon=recon,
        report=report,
    )
    assert voucher.is_draft is True
    assert voucher.requires_account_mapping is True
    assert voucher.is_balanced is True
    assert voucher.total_debits == 50000.0
    assert voucher.total_credits == 50000.0
    assert len(voucher.lines) == 2


def test_partial_settlement_allocates_shortfall(partial_case):
    recon, report = partial_case
    voucher = DraftJournalEngine.generate_draft_voucher(
        case_id="CASE-PRT",
        recon=recon,
        report=report,
    )
    assert voucher.is_balanced is True
    assert voucher.total_debits == 50000.0
    assert voucher.total_credits == 50000.0
    assert len(voucher.lines) == 3
    dr_amounts = [l.debit_amount for l in voucher.lines if l.debit_amount > 0]
    assert 30000.0 in dr_amounts
    assert 20000.0 in dr_amounts


def test_custom_coa_mapping_profile(clean_case):
    recon, report = clean_case
    custom_coa = {
        "bank_clearing": {"code": "GL-ICICI-100", "name": "ICICI Primary Bank"},
        "vendor_payable": {"code": "GL-AP-999", "name": "Trade Creditors"},
    }
    voucher = DraftJournalEngine.generate_draft_voucher(
        case_id="CASE-CLN",
        recon=recon,
        report=report,
        custom_coa_mapping=custom_coa,
    )
    assert voucher.requires_account_mapping is False
    assert voucher.coa_mapping_profile == "CUSTOM_CONFIGURED_COA"
    codes = {l.account_code for l in voucher.lines}
    assert "GL-ICICI-100" in codes
    assert "GL-AP-999" in codes
