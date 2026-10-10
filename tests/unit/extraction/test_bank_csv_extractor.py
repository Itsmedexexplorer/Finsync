"""Unit tests for BankCSVExtractor in VERITY Extraction Subsystem."""

import pytest
from backend.domain.claim import ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.extraction.bank_csv_extractor import BankCSVExtractor
from backend.extraction.result import ExtractionStatus


@pytest.fixture
def bank_extractor() -> BankCSVExtractor:
    return BankCSVExtractor()


def test_bank_csv_extractor_credit_row(bank_extractor: BankCSVExtractor) -> None:
    ev = Evidence(
        id="EVID-CSV-001",
        modality=EvidenceModality.BANK_STATEMENT,
        source_type=EvidenceSourceType.BANK_CSV,
        source_name="statement.csv:Row2",
        raw_payload="15/08/2026,UPI/408219381920/PAYTO/ROHIT VERMA/HDFC,35000.00,0.00,185000.00",
        metadata={
            "row_index": 2,
            "normalized_fields": {
                "date": "15/08/2026",
                "narration": "UPI/408219381920/PAYTO/ROHIT VERMA/HDFC",
                "credit": "35000.00",
                "debit": "0.00",
                "reference": "408219381920",
            }
        }
    )

    result = bank_extractor.extract(ev)
    assert result.status == ExtractionStatus.SUCCESS
    assert len(result.claims) == 1

    claim = result.claims[0]
    assert claim.evidence_id == "EVID-CSV-001"
    assert claim.claim_type == ClaimType.PAYMENT_RECEIVED
    assert claim.claimed_amount == 35000.0
    assert claim.claimed_date == "15/08/2026"
    assert claim.reference_id_hint == "408219381920"
    assert claim.payment_method_hint == "UPI"
    assert claim.counterparty_hint == "ROHIT VERMA"
    assert claim.confidence == 1.0


def test_bank_csv_extractor_debit_row(bank_extractor: BankCSVExtractor) -> None:
    ev = Evidence(
        id="EVID-CSV-002",
        modality=EvidenceModality.BANK_STATEMENT,
        source_type=EvidenceSourceType.BANK_CSV,
        source_name="statement.csv:Row3",
        raw_payload="16/08/2026,NEFT/NEFTN26235889012/POOJAPLASTICS/ICICI,0.00,125000.00,60000.00",
        metadata={
            "row_index": 3,
            "normalized_fields": {
                "date": "16/08/2026",
                "narration": "NEFT/NEFTN26235889012/POOJAPLASTICS/ICICI",
                "credit": "0.00",
                "debit": "125000.00",
                "reference": "NEFTN26235889012",
            }
        }
    )

    result = bank_extractor.extract(ev)
    assert result.status == ExtractionStatus.SUCCESS
    assert len(result.claims) == 1

    claim = result.claims[0]
    assert claim.claim_type == ClaimType.PAYMENT_SENT
    assert claim.claimed_amount == 125000.0
    assert claim.payment_method_hint == "NEFT"
    assert claim.reference_id_hint == "NEFTN26235889012"
    assert claim.counterparty_hint == "POOJAPLASTICS"


def test_bank_csv_extractor_incompatible_modality(bank_extractor: BankCSVExtractor) -> None:
    ev = Evidence(
        id="EVID-TXT-001",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="chat.txt",
        raw_payload="Bhai 20k GPay kar diya",
    )

    result = bank_extractor.extract(ev)
    assert result.status == ExtractionStatus.EXTRACTION_ERROR
    assert len(result.claims) == 0
