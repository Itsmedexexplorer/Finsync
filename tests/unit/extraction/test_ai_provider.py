"""Unit tests for AIExtractionProvider and structured JSON schema validation."""

import json
import pytest
from backend.domain.claim import ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.extraction.ai_provider import (
    AIExtractionProvider,
    AIProviderConfig,
    AIProviderType,
)
from backend.extraction.result import ExtractionStatus


def test_ai_provider_valid_structured_response() -> None:
    def mock_invoker(raw_text: str) -> str:
        return json.dumps({
            "claims": [{
                "claim_type": "PAYMENT_SENT",
                "amount": 25000.0,
                "currency": "INR",
                "claimed_date": "2026-08-15",
                "counterparty_hint": "Ramesh Tech",
                "reference_id_hint": "408219381920",
                "payment_method_hint": "UPI",
                "confidence": 0.95,
                "raw_text_snippet": "Bhai 25k GPay kar diya",
                "reasoning": "Explicit 25k payment via GPay.",
            }],
            "detected_language": "hinglish",
            "is_financial_evidence": True,
        })

    config = AIProviderConfig(provider_type=AIProviderType.MOCK, model_name="test-model")
    provider = AIExtractionProvider(config=config, mock_invoker=mock_invoker)

    ev = Evidence(
        id="EVID-AI-001",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="chat.txt",
        raw_payload="Bhai 25k GPay kar diya check kar lo",
    )

    result = provider.extract(ev)
    assert result.status == ExtractionStatus.SUCCESS
    assert len(result.claims) == 1

    claim = result.claims[0]
    assert claim.evidence_id == "EVID-AI-001"
    assert claim.claim_type == ClaimType.PAYMENT_SENT
    assert claim.claimed_amount == 25000.0
    assert claim.counterparty_hint == "Ramesh Tech"
    assert claim.reference_id_hint == "408219381920"
    assert claim.confidence == 0.95


def test_ai_provider_malformed_json_handling() -> None:
    def broken_invoker(raw_text: str) -> str:
        return "Not valid JSON output at all"

    config = AIProviderConfig(provider_type=AIProviderType.MOCK)
    provider = AIExtractionProvider(config=config, mock_invoker=broken_invoker)

    ev = Evidence(
        id="EVID-AI-002",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="chat.txt",
        raw_payload="Testing broken response",
    )

    result = provider.extract(ev)
    assert result.status == ExtractionStatus.EXTRACTION_ERROR
    assert len(result.claims) == 0
    assert len(result.errors) > 0


def test_ai_provider_missing_api_key_for_live_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure env var is absent
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    
    config = AIProviderConfig(
        provider_type=AIProviderType.OPENAI_COMPATIBLE,
        api_key_env_var="OPENAI_API_KEY",
        model_name="gpt-4o-mini",
    )
    provider = AIExtractionProvider(config=config)

    ev = Evidence(
        id="EVID-AI-003",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="chat.txt",
        raw_payload="Payment sent",
    )

    result = provider.extract(ev)
    assert result.status == ExtractionStatus.PROVIDER_UNAVAILABLE
    assert "OPENAI_API_KEY" in result.errors[0]


def test_ai_provider_non_financial_content() -> None:
    def non_financial_invoker(raw_text: str) -> str:
        return json.dumps({
            "claims": [],
            "is_financial_evidence": False,
            "detected_language": "en"
        })

    config = AIProviderConfig(provider_type=AIProviderType.MOCK)
    provider = AIExtractionProvider(config=config, mock_invoker=non_financial_invoker)

    ev = Evidence(
        id="EVID-AI-004",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="chat.txt",
        raw_payload="Hello good morning!",
    )

    result = provider.extract(ev)
    assert result.status == ExtractionStatus.NO_CLAIMS_FOUND
    assert len(result.claims) == 0
