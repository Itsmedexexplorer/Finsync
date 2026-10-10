"""Provider-independent AI/VLM Extraction Engine for VERITY.

Provides structured schema-constrained financial extraction with strict anti-hallucination
safeguards, supporting OpenAI-compatible, Gemini, custom, and mock providers.

Day 17: Real multimodal extraction — image/VLM support via google-genai SDK.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field, ValidationError

from backend.domain.claim import Claim, ClaimStatus, ClaimType
from backend.domain.evidence import Evidence, EvidenceModality
from backend.extraction.base import BaseExtractor
from backend.extraction.result import ExtractionResult, ExtractionStatus, ExtractionWarning

logger = logging.getLogger(__name__)


class AIProviderType(str, Enum):
    """Supported AI/VLM provider types."""
    MOCK = "MOCK"
    OPENAI_COMPATIBLE = "OPENAI_COMPATIBLE"
    GEMINI = "GEMINI"
    CUSTOM = "CUSTOM"


class AIProviderConfig(BaseModel):
    """Configuration for AI extraction provider."""
    provider_type: AIProviderType = Field(default=AIProviderType.MOCK)
    api_key_env_var: str = Field(default="VERITY_AI_API_KEY")
    model_name: str = Field(default="gpt-4o-mini")
    timeout_seconds: int = Field(default=15, ge=1)
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    endpoint_url: Optional[str] = Field(default=None)


class RawClaimOutput(BaseModel):
    """Pydantic model representing an individual claim extracted by an AI model."""
    claim_type: ClaimType = Field(..., description="Type of financial assertion")
    amount: Optional[float] = Field(
        default=None,
        description="Explicit numeric amount in evidence. Must be NULL if not stated."
    )
    currency: str = Field(default="INR", description="Three-letter ISO currency code")
    claimed_date: Optional[str] = Field(
        default=None,
        description="Date asserted in evidence. Must be NULL if not stated."
    )
    counterparty_hint: Optional[str] = Field(
        default=None,
        description="Name, handle, or phone of other party. Must be NULL if not stated."
    )
    reference_id_hint: Optional[str] = Field(
        default=None,
        description="UTR, RRN, invoice # or cheque ref. Must be NULL if not stated."
    )
    payment_method_hint: Optional[str] = Field(
        default=None,
        description="Asserted payment rail (e.g. 'UPI', 'NEFT', 'CASH')."
    )
    confidence: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Model confidence score (0.0 to 1.0)."
    )
    raw_text_snippet: Optional[str] = Field(
        default=None,
        description="Verbatim text supporting this claim."
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Concise justification of the extraction."
    )


class StructuredClaimExtractionOutput(BaseModel):
    """Top-level structured JSON schema for AI extraction responses."""
    claims: List[RawClaimOutput] = Field(
        default_factory=list,
        description="List of factual claims explicitly stated in the evidence."
    )
    detected_language: Optional[str] = Field(default="en")
    is_financial_evidence: bool = Field(
        default=True,
        description="False if the evidence is casual chit-chat with no financial facts."
    )


EXTRACTION_SYSTEM_PROMPT = """You are VERITY's Financial Evidence Extraction Engine.
Your task is to extract structured financial claims from raw evidence (messages, invoices, receipts, screenshots).

CRITICAL ANTI-HALLUCINATION RULES:
1. Extract ONLY facts that are EXPLICITLY stated in the evidence.
2. If the amount is NOT stated (e.g. "I sent the money"), set amount to null. NEVER guess or invent amounts.
3. If the counterparty is NOT stated (e.g. "Payment received"), set counterparty_hint to null.
4. If no reference ID or date is stated, set them to null.
5. If the evidence contains casual greetings or no financial content, return an empty claims list.
6. Output must strictly conform to the StructuredClaimExtractionOutput JSON schema.
7. For Hinglish/code-mixed text: "k" means thousand, "hazar"/"हजार" means thousand, "lakh" means 100000.
8. Common Hinglish: "bhej diya" = sent, "kar diya" = done, "UPI kiya" = UPI transfer done.
9. Relative dates like "kal" (yesterday/tomorrow), "parso" (day before/after yesterday): preserve as-is in claimed_date if no absolute date can be determined.
10. For images/screenshots: extract only what is VISIBLY present. Do not infer hidden information.

Respond with valid JSON matching this schema:
{
  "claims": [
    {
      "claim_type": "PAYMENT_SENT" | "PAYMENT_RECEIVED" | "INVOICE_ISSUED" | "CASH_PAYMENT_PROMISE" | "REFUND_REQUESTED" | "DISCOUNT_APPLIED" | "EXPENSE_INCURRED",
      "amount": <float or null>,
      "currency": "INR",
      "claimed_date": "<date string or null>",
      "counterparty_hint": "<string or null>",
      "reference_id_hint": "<string or null>",
      "payment_method_hint": "<string or null>",
      "confidence": <0.0 to 1.0>,
      "raw_text_snippet": "<verbatim source text>",
      "reasoning": "<brief justification>"
    }
  ],
  "detected_language": "en" | "hi" | "hinglish" | ...,
  "is_financial_evidence": true | false
}"""


class AIExtractionProvider(BaseExtractor):
    """Provider-independent AI Extractor with strict schema validation."""

    def __init__(
        self,
        config: Optional[AIProviderConfig] = None,
        mock_invoker: Optional[Callable[[str], str]] = None,
    ) -> None:
        self.config = config or AIProviderConfig()
        self.mock_invoker = mock_invoker
        self._gemini_client = None

    @property
    def provider_name(self) -> str:
        return f"ai_{self.config.provider_type.value.lower()}_{self.config.model_name}"

    def can_extract(self, evidence: Evidence) -> bool:
        # AI extractor can handle any unstructured or multimodal evidence
        return True

    def extract(
        self,
        evidence: Evidence,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExtractionResult:
        # Check API key configuration for live providers
        if self.config.provider_type != AIProviderType.MOCK:
            api_key = (
                os.environ.get(self.config.api_key_env_var)
                or os.environ.get("GEMINI_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
                or os.environ.get("VERITY_AI_API_KEY")
            )
            if not api_key:
                return ExtractionResult.create_failure(
                    evidence_id=evidence.id,
                    status=ExtractionStatus.PROVIDER_UNAVAILABLE,
                    error_message=(
                        f"AI extraction provider '{self.config.provider_type.value}' requires "
                        f"environment variable '{self.config.api_key_env_var}' (or GEMINI_API_KEY / GOOGLE_API_KEY), which is not set."
                    ),
                    provider_name=self.provider_name,
                )

        try:
            raw_json_response = self._call_model(evidence)
            parsed_output = self._validate_and_parse_response(raw_json_response)
        except ValidationError as val_err:
            return ExtractionResult.create_failure(
                evidence_id=evidence.id,
                status=ExtractionStatus.EXTRACTION_ERROR,
                error_message=f"AI provider returned structured output failing schema validation: {val_err}",
                provider_name=self.provider_name,
            )
        except Exception as exc:
            return ExtractionResult.create_failure(
                evidence_id=evidence.id,
                status=ExtractionStatus.EXTRACTION_ERROR,
                error_message=f"AI model call failed: {exc}",
                provider_name=self.provider_name,
            )

        if not parsed_output.is_financial_evidence or not parsed_output.claims:
            return ExtractionResult(
                evidence_id=evidence.id,
                status=ExtractionStatus.NO_CLAIMS_FOUND,
                claims=[],
                provider_name=self.provider_name,
                confidence_score=1.0,
            )

        # Convert RawClaimOutput into canonical domain Claim objects
        canonical_claims: List[Claim] = []
        for raw_claim in parsed_output.claims:
            try:
                claim_id = f"CLM-AI-{uuid.uuid4().hex[:8]}"
                c = Claim(
                    id=claim_id,
                    evidence_id=evidence.id,
                    claim_type=raw_claim.claim_type,
                    claimed_amount=raw_claim.amount,
                    currency=raw_claim.currency or "INR",
                    claimed_date=raw_claim.claimed_date,
                    counterparty_hint=raw_claim.counterparty_hint,
                    reference_id_hint=raw_claim.reference_id_hint,
                    payment_method_hint=raw_claim.payment_method_hint,
                    confidence=round(raw_claim.confidence, 2),
                    raw_text_snippet=raw_claim.raw_text_snippet or evidence.raw_payload[:200],
                    status=ClaimStatus.ASSERTED,
                    metadata={
                        "model_reasoning": raw_claim.reasoning,
                        "provider": self.provider_name,
                    },
                )
                canonical_claims.append(c)
            except (ValidationError, ValueError) as claim_err:
                logger.warning(
                    "Rejected AI-extracted claim due to validation failure: %s", claim_err
                )
                return ExtractionResult.create_failure(
                    evidence_id=evidence.id,
                    status=ExtractionStatus.EXTRACTION_ERROR,
                    error_message=f"AI-extracted claim failed domain validation: {claim_err}",
                    provider_name=self.provider_name,
                )

        avg_confidence = (
            sum(c.confidence for c in canonical_claims) / len(canonical_claims)
            if canonical_claims else 1.0
        )

        return ExtractionResult.create_success(
            evidence_id=evidence.id,
            claims=canonical_claims,
            provider_name=self.provider_name,
            confidence_score=round(avg_confidence, 2),
            metadata={"language": parsed_output.detected_language},
        )

    # ------------------------------------------------------------------
    # MODEL INVOCATION
    # ------------------------------------------------------------------

    def _call_model(self, evidence: Evidence) -> str:
        """Invokes the model or mock handler to obtain structured JSON."""
        if self.config.provider_type == AIProviderType.MOCK:
            if self.mock_invoker:
                return self.mock_invoker(evidence.raw_payload)
            # Default mock behavior based on content
            return self._default_mock_response(evidence)

        if self.config.provider_type == AIProviderType.GEMINI:
            return self._call_gemini(evidence)

        if self.config.provider_type == AIProviderType.OPENAI_COMPATIBLE:
            return self._call_openai_compatible(evidence)

        raise NotImplementedError(
            f"Provider type '{self.config.provider_type.value}' is not yet implemented."
        )

    # ------------------------------------------------------------------
    # GEMINI PROVIDER (google-genai SDK)
    # ------------------------------------------------------------------

    def _get_gemini_client(self) -> Any:
        """Lazy-initialize Gemini client."""
        if self._gemini_client is None:
            try:
                from google import genai
                api_key = (
                    os.environ.get(self.config.api_key_env_var)
                    or os.environ.get("GEMINI_API_KEY")
                    or os.environ.get("GOOGLE_API_KEY")
                    or os.environ.get("VERITY_AI_API_KEY")
                )
                self._gemini_client = genai.Client(api_key=api_key)
            except ImportError:
                raise RuntimeError(
                    "google-genai package is required for Gemini provider. "
                    "Install with: pip install google-genai"
                )
        return self._gemini_client

    def _call_gemini(self, evidence: Evidence) -> str:
        """Call Google Gemini with text and/or image content."""
        from google.genai import types

        client = self._get_gemini_client()
        model_name = self.config.model_name

        # Build multimodal content parts
        content_parts: List[Any] = []

        # Check for image data in evidence metadata
        image_b64 = evidence.metadata.get("image_bytes_b64")
        page_images = evidence.metadata.get("page_images_b64", [])
        mime_type = evidence.metadata.get("mime_type", "image/png")

        if image_b64:
            # Single image evidence (payment screenshot, receipt photo)
            image_bytes = base64.b64decode(image_b64)
            content_parts.append(types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type,
            ))
            content_parts.append(types.Part.from_text(
                text=(
                    f"Extract financial claims from this payment screenshot/receipt image.\n"
                    f"Source: {evidence.source_name}\n"
                    f"Evidence ID: {evidence.id}\n\n"
                    f"{EXTRACTION_SYSTEM_PROMPT}"
                )
            ))
        elif page_images:
            # Scanned PDF with extracted page images
            for page_img in page_images:
                img_bytes = base64.b64decode(page_img["image_b64"])
                content_parts.append(types.Part.from_bytes(
                    data=img_bytes,
                    mime_type=page_img.get("mime_type", "image/png"),
                ))
            content_parts.append(types.Part.from_text(
                text=(
                    f"Extract financial claims from this scanned PDF document.\n"
                    f"Source: {evidence.source_name}\n"
                    f"Pages: {len(page_images)}\n"
                    f"Evidence ID: {evidence.id}\n\n"
                    f"{EXTRACTION_SYSTEM_PROMPT}"
                )
            ))
        else:
            # Text-only evidence
            content_parts.append(types.Part.from_text(
                text=(
                    f"Extract financial claims from the following text evidence:\n\n"
                    f"---\n{evidence.raw_payload}\n---\n\n"
                    f"Source: {evidence.source_name}\n"
                    f"Evidence ID: {evidence.id}\n\n"
                    f"{EXTRACTION_SYSTEM_PROMPT}"
                )
            ))

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=content_parts,
                config=types.GenerateContentConfig(
                    temperature=self.config.temperature,
                    response_mime_type="application/json",
                ),
            )
            result_text = response.text
            if not result_text:
                raise RuntimeError("Gemini returned empty response")
            logger.info(
                "Gemini extraction complete for evidence %s (model=%s, chars=%d)",
                evidence.id, model_name, len(result_text),
            )
            return result_text

        except Exception as exc:
            logger.error("Gemini API call failed for evidence %s: %s", evidence.id, exc)
            raise

    # ------------------------------------------------------------------
    # OPENAI-COMPATIBLE PROVIDER (httpx)
    # ------------------------------------------------------------------

    def _call_openai_compatible(self, evidence: Evidence) -> str:
        """Call OpenAI-compatible endpoint with text content."""
        import httpx

        api_key = os.environ.get(self.config.api_key_env_var)
        endpoint = self.config.endpoint_url or "https://api.openai.com/v1/chat/completions"

        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract financial claims from:\n\n{evidence.raw_payload}"},
        ]

        # If image data available, add as base64 image_url content
        image_b64 = evidence.metadata.get("image_bytes_b64")
        mime_type = evidence.metadata.get("mime_type", "image/png")
        if image_b64:
            messages[-1] = {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Extract financial claims from this image.\nSource: {evidence.source_name}"},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
                ],
            }

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "response_format": {"type": "json_object"},
        }

        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                resp = client.post(
                    endpoint,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.error("OpenAI-compatible API call failed: %s", exc)
            raise

    # ------------------------------------------------------------------
    # RESPONSE VALIDATION
    # ------------------------------------------------------------------

    def _validate_and_parse_response(self, raw_response: str) -> StructuredClaimExtractionOutput:
        """Parses and validates JSON response against Pydantic schema."""
        # Strip potential markdown code fences ```json ... ```
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        data = json.loads(cleaned)
        return StructuredClaimExtractionOutput.model_validate(data)

    # ------------------------------------------------------------------
    # MOCK PROVIDER
    # ------------------------------------------------------------------

    def _default_mock_response(self, evidence: Evidence) -> str:
        """Built-in deterministic mock response for testing without live API keys."""
        text = evidence.raw_payload
        if "I sent the money" in text:
            return json.dumps({
                "claims": [{
                    "claim_type": "PAYMENT_SENT",
                    "amount": None,
                    "counterparty_hint": None,
                    "payment_method_hint": None,
                    "confidence": 0.7,
                    "reasoning": "Payment sent stated without amount or counterparty."
                }],
                "is_financial_evidence": True
            })
        elif "Payment of ₹18,500 received from Rahul" in text or "18,500" in text:
            return json.dumps({
                "claims": [{
                    "claim_type": "PAYMENT_RECEIVED",
                    "amount": 18500.0,
                    "counterparty_hint": "Rahul",
                    "payment_method_hint": None,
                    "confidence": 0.98,
                    "reasoning": "Explicit receipt of 18500 from Rahul."
                }],
                "is_financial_evidence": True
            })
        # Image evidence mock — check if it has image data in metadata
        elif evidence.metadata.get("image_bytes_b64"):
            return json.dumps({
                "claims": [{
                    "claim_type": "PAYMENT_SENT",
                    "amount": None,
                    "counterparty_hint": None,
                    "payment_method_hint": "UPI",
                    "confidence": 0.6,
                    "raw_text_snippet": f"[Image: {evidence.source_name}]",
                    "reasoning": "Image evidence detected, mock extraction — real VLM required for actual values."
                }],
                "is_financial_evidence": True
            })
        # Scanned PDF mock — check for page images
        elif evidence.metadata.get("page_images_b64"):
            return json.dumps({
                "claims": [{
                    "claim_type": "INVOICE_ISSUED",
                    "amount": None,
                    "counterparty_hint": None,
                    "confidence": 0.5,
                    "raw_text_snippet": f"[Scanned PDF: {evidence.source_name}]",
                    "reasoning": "Scanned PDF detected, mock extraction — real VLM required for actual values."
                }],
                "is_financial_evidence": True
            })
        return json.dumps({
            "claims": [],
            "is_financial_evidence": False
        })
