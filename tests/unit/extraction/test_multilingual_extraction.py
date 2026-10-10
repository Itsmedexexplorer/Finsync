"""Unit tests for Multilingual Financial Claim Extraction."""

import pytest
from backend.domain.claim import ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.extraction.text_extractor import TextClaimExtractor


@pytest.fixture
def text_extractor() -> TextClaimExtractor:
    return TextClaimExtractor()


def test_multilingual_hindi_devanagari(text_extractor: TextClaimExtractor) -> None:
    ev = Evidence(
        id="EVID-HI-001",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="chat.txt",
        raw_payload="नमस्ते, मैंने बीस हज़ार रुपये गूगल पे कर दिए हैं। संदर्भ सं 408219381921",
        language_hint="hi",
    )

    res = text_extractor.extract(ev)
    assert len(res.claims) == 1
    claim = res.claims[0]
    assert claim.claim_type == ClaimType.PAYMENT_SENT
    assert claim.claimed_amount == 20000.0
    assert claim.reference_id_hint == "408219381921"


def test_multilingual_marathi(text_extractor: TextClaimExtractor) -> None:
    ev = Evidence(
        id="EVID-MR-001",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="chat.txt",
        raw_payload="काल 20 हजार पाठवले चेक करा",
        language_hint="mr",
    )

    res = text_extractor.extract(ev)
    assert len(res.claims) == 1
    assert res.claims[0].claim_type == ClaimType.PAYMENT_SENT
    assert res.claims[0].claimed_amount == 20000.0


def test_multilingual_tamil(text_extractor: TextClaimExtractor) -> None:
    ev = Evidence(
        id="EVID-TA-001",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="chat.txt",
        raw_payload="GPay paniten 12500 check pannunga bro ref 408219381923",
        language_hint="ta-Latn",
    )

    res = text_extractor.extract(ev)
    assert len(res.claims) == 1
    claim = res.claims[0]
    assert claim.claim_type == ClaimType.PAYMENT_SENT
    assert claim.claimed_amount == 12500.0
    assert claim.payment_method_hint == "UPI"
    assert claim.reference_id_hint == "408219381923"


def test_multilingual_kannada_and_telugu(text_extractor: TextClaimExtractor) -> None:
    # Kannada
    ev_kn = Evidence(
        id="EVID-KN-001",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="chat.txt",
        raw_payload="Hana kalsiddini 18000 PhonePe check maadi ref 408219381925",
        language_hint="kn-Latn",
    )
    res_kn = text_extractor.extract(ev_kn)
    assert res_kn.claims[0].claimed_amount == 18000.0
    assert res_kn.claims[0].claim_type == ClaimType.PAYMENT_SENT

    # Telugu
    ev_te = Evidence(
        id="EVID-TE-001",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="chat.txt",
        raw_payload="GPay chesanu 22000 chusukondi ref 408219381927",
        language_hint="te-Latn",
    )
    res_te = text_extractor.extract(ev_te)
    assert res_te.claims[0].claimed_amount == 22000.0
    assert res_te.claims[0].reference_id_hint == "408219381927"
