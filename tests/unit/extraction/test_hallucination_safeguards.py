"""Unit tests verifying strict anti-hallucination safeguards in extraction."""

import pytest
from backend.domain.claim import ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.extraction.text_extractor import TextClaimExtractor


@pytest.fixture
def text_extractor() -> TextClaimExtractor:
    return TextClaimExtractor()


def test_hallucination_safeguard_sent_without_amount(text_extractor: TextClaimExtractor) -> None:
    """Evidence: 'I sent the money.' -> Expected: amount = UNKNOWN (None). Never guess an amount."""
    ev = Evidence(
        id="EVID-TEST-H1",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="chat.txt",
        raw_payload="I sent the money.",
    )

    res = text_extractor.extract(ev)
    assert len(res.claims) == 1
    claim = res.claims[0]
    assert claim.claim_type == ClaimType.PAYMENT_SENT
    assert claim.claimed_amount is None  # UNKNOWN
    assert claim.counterparty_hint is None
    assert claim.reference_id_hint is None


def test_hallucination_safeguard_received_without_counterparty_or_amount(text_extractor: TextClaimExtractor) -> None:
    """Evidence: 'Payment received.' -> Expected: counterparty = UNKNOWN, amount = UNKNOWN."""
    ev = Evidence(
        id="EVID-TEST-H2",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.SMS_TEXT,
        source_name="sms.txt",
        raw_payload="Payment received.",
    )

    res = text_extractor.extract(ev)
    assert len(res.claims) == 1
    claim = res.claims[0]
    assert claim.claim_type == ClaimType.PAYMENT_RECEIVED
    assert claim.claimed_amount is None  # UNKNOWN
    assert claim.counterparty_hint is None  # UNKNOWN


def test_hallucination_safeguard_exact_amount_when_stated(text_extractor: TextClaimExtractor) -> None:
    """Evidence: '₹20,000 sent.' -> Expected: amount = 20000.0, claim_type = PAYMENT_SENT."""
    ev = Evidence(
        id="EVID-TEST-H3",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="chat.txt",
        raw_payload="₹20,000 sent.",
    )

    res = text_extractor.extract(ev)
    assert len(res.claims) == 1
    claim = res.claims[0]
    assert claim.claim_type == ClaimType.PAYMENT_SENT
    assert claim.claimed_amount == 20000.0
    assert claim.counterparty_hint is None  # Counterparty not stated -> None


def test_hallucination_safeguard_no_unsupported_references(text_extractor: TextClaimExtractor) -> None:
    """Evidence: 'Transferred Rs 5000 to shopkeeper' -> reference_id must be None since no UTR was stated."""
    ev = Evidence(
        id="EVID-TEST-H4",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="chat.txt",
        raw_payload="Transferred Rs 5000 to shopkeeper yesterday",
    )

    res = text_extractor.extract(ev)
    assert len(res.claims) == 1
    claim = res.claims[0]
    assert claim.claimed_amount == 5000.0
    assert claim.reference_id_hint is None  # Must NOT hallucinate a UTR number
