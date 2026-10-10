"""Unit tests for TextClaimExtractor in VERITY Extraction Subsystem."""

import pytest
from backend.domain.claim import ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.extraction.result import ExtractionStatus
from backend.extraction.text_extractor import TextClaimExtractor


@pytest.fixture
def text_extractor() -> TextClaimExtractor:
    return TextClaimExtractor()


def test_text_extractor_standard_english_payment_received(text_extractor: TextClaimExtractor) -> None:
    ev = Evidence(
        id="EVID-TXT-001",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.SMS_TEXT,
        source_name="sms_alert.txt",
        raw_payload="Payment of ₹18,500 received from Rahul via UPI ref: 408219381920.",
    )

    result = text_extractor.extract(ev)
    assert result.status == ExtractionStatus.SUCCESS
    assert len(result.claims) == 1

    claim = result.claims[0]
    assert claim.evidence_id == "EVID-TXT-001"
    assert claim.claim_type == ClaimType.PAYMENT_RECEIVED
    assert claim.claimed_amount == 18500.0
    assert claim.counterparty_hint == "Rahul"
    assert claim.payment_method_hint == "UPI"
    assert claim.reference_id_hint == "408219381920"


def test_text_extractor_k_and_lakh_notations(text_extractor: TextClaimExtractor) -> None:
    # 20k format
    ev1 = Evidence(
        id="EVID-K-001",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="chat.txt",
        raw_payload="Bhai 20k GPay kar diya check kar lo",
    )
    res1 = text_extractor.extract(ev1)
    assert res1.status == ExtractionStatus.SUCCESS
    assert res1.claims[0].claimed_amount == 20000.0
    assert res1.claims[0].payment_method_hint == "UPI"
    assert res1.claims[0].claim_type == ClaimType.PAYMENT_SENT

    # 1.5 Lakh format
    ev2 = Evidence(
        id="EVID-L-001",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="chat.txt",
        raw_payload="Transferred 1.5 lakh via NEFT for material supply",
    )
    res2 = text_extractor.extract(ev2)
    assert res2.status == ExtractionStatus.SUCCESS
    assert res2.claims[0].claimed_amount == 150000.0
    assert res2.claims[0].payment_method_hint == "NEFT"


def test_text_extractor_cash_payment_promise(text_extractor: TextClaimExtractor) -> None:
    ev = Evidence(
        id="EVID-CASH-001",
        modality=EvidenceModality.CASH_VOUCHER,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="cash.txt",
        raw_payload="Bhai office me 10,000 cash de diya tha boy ko",
    )

    result = text_extractor.extract(ev)
    assert result.status == ExtractionStatus.SUCCESS
    assert len(result.claims) == 1
    assert result.claims[0].claim_type == ClaimType.CASH_PAYMENT_PROMISE
    assert result.claims[0].claimed_amount == 10000.0
    assert result.claims[0].payment_method_hint == "CASH"


def test_text_extractor_non_financial_text_no_claims(text_extractor: TextClaimExtractor) -> None:
    ev = Evidence(
        id="EVID-CASUAL-001",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="chat.txt",
        raw_payload="Good morning Rameshji, will call you later today.",
    )

    result = text_extractor.extract(ev)
    assert result.status == ExtractionStatus.NO_CLAIMS_FOUND
    assert len(result.claims) == 0


def test_text_extractor_romanized_hinglish_payment_sent(text_extractor: TextClaimExtractor) -> None:
    ev = Evidence(
        id="EVID-TXT-HING",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.SMS_TEXT,
        source_name="chat.txt",
        raw_payload="Vikram: Namaste, maine 15000 google pay kar diye hain. UTR: 419082390192",
    )

    result = text_extractor.extract(ev)
    assert result.status == ExtractionStatus.SUCCESS
    claim = result.claims[0]
    assert claim.claim_type == ClaimType.PAYMENT_SENT
    assert claim.claimed_amount == 15000.0
    assert claim.reference_id_hint == "419082390192"
