"""Day 17 — Multimodal Extraction Tests.

Tests covering:
- Image ingestion with base64 data preservation
- Scanned PDF page image extraction
- Mock provider handling of image/PDF evidence
- Relative date resolution with reference timestamps
- Enhanced Hinglish extraction
- Schema validation and hallucination rejection
- Extraction safety (malformed AI output, provider failure)
- End-to-end pipeline integration (messy evidence → claims → deterministic truth)

Test Categories:
  A. MOCK PROVIDER TESTS — always runnable
  B. LOCAL FIXTURE IMAGE/PDF PIPELINE TESTS — require generated fixtures
  C. LIVE GEMINI TESTS — only run when GEMINI_API_KEY is available
"""

from __future__ import annotations

import base64
import io
import json
import os
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict

import pytest
from PIL import Image

from backend.domain.claim import Claim, ClaimStatus, ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.entity import Entity
from backend.domain.transaction import Transaction
from backend.extraction.ai_provider import (
    AIExtractionProvider,
    AIProviderConfig,
    AIProviderType,
    StructuredClaimExtractionOutput,
)
from backend.extraction.result import ExtractionResult, ExtractionStatus
from backend.extraction.service import ExtractionService
from backend.extraction.text_extractor import TextClaimExtractor
from backend.ingestion.image_adapter import ImagePaymentScreenshotAdapter
from backend.ingestion.pdf_adapter import PDFDocumentAdapter
from backend.ingestion.service import IngestionService


# ============================================================
# HELPERS
# ============================================================

FIXTURE_DIR = Path("data/samples/day17/fixtures")


def _make_test_png_bytes(text: str = "Test Image", width: int = 200, height: int = 100) -> bytes:
    """Create a minimal valid PNG image in-memory."""
    img = Image.new("RGB", (width, height), color=(200, 200, 200))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.text((10, 40), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_text_evidence(text: str, ev_id: str = "", **extra_meta: Any) -> Evidence:
    """Create a text Evidence object."""
    return Evidence(
        id=ev_id or f"EVID-TEST-{uuid.uuid4().hex[:8]}",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="test_chat.txt",
        raw_payload=text,
        language_hint="hinglish",
        metadata=extra_meta,
    )


# ============================================================
# A. IMAGE INGESTION — BASE64 PRESERVATION
# ============================================================

class TestImageBase64Preservation:
    """Verify that image bytes are preserved as base64 in Evidence metadata."""

    def test_image_adapter_stores_base64(self) -> None:
        adapter = ImagePaymentScreenshotAdapter()
        png_bytes = _make_test_png_bytes("UPI Payment ₹25,000")

        result = adapter.ingest_payload(
            raw_content=png_bytes,
            source_name="upi_screenshot.png",
        )

        assert result.status.value == "SUCCESS"
        assert len(result.evidence_items) == 1
        ev = result.evidence_items[0]

        # Base64 data must be present
        assert "image_bytes_b64" in ev.metadata
        decoded = base64.b64decode(ev.metadata["image_bytes_b64"])
        assert len(decoded) > 0

        # Verify the decoded bytes are a valid image
        img = Image.open(io.BytesIO(decoded))
        assert img.size == (200, 100)

        # MIME type must be present
        assert ev.metadata.get("mime_type") == "image/png"

    def test_image_adapter_jpeg_base64(self) -> None:
        adapter = ImagePaymentScreenshotAdapter()
        img = Image.new("RGB", (100, 100), color=(255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        jpeg_bytes = buf.getvalue()

        result = adapter.ingest_payload(
            raw_content=jpeg_bytes,
            source_name="bank_screenshot.jpg",
        )

        assert result.status.value == "SUCCESS"
        ev = result.evidence_items[0]
        assert "image_bytes_b64" in ev.metadata
        assert ev.metadata["mime_type"] == "image/jpeg"

    def test_raw_payload_remains_text_placeholder(self) -> None:
        """raw_payload should still be a text description, not binary data."""
        adapter = ImagePaymentScreenshotAdapter()
        png_bytes = _make_test_png_bytes()

        result = adapter.ingest_payload(raw_content=png_bytes, source_name="test.png")
        ev = result.evidence_items[0]

        assert "[IMAGE_ARTIFACT:" in ev.raw_payload
        assert "PNG" in ev.raw_payload


# ============================================================
# B. SCANNED PDF — PAGE IMAGE EXTRACTION
# ============================================================

class TestScannedPDFImageExtraction:
    """Verify that scanned PDFs have page images extracted as base64."""

    def test_scanned_pdf_from_fixture(self) -> None:
        """Test with the actual generated scanned PDF fixture."""
        pdf_path = FIXTURE_DIR / "scanned_receipt.pdf"
        if not pdf_path.exists():
            pytest.skip("Day 17 fixtures not generated — run scripts/create_day17_fixtures.py")

        adapter = PDFDocumentAdapter()
        result = adapter.ingest_file(pdf_path)

        assert result.status.value == "SUCCESS"
        ev = result.evidence_items[0]
        assert ev.metadata.get("is_scanned") is True

        # Page images should be extracted
        page_images = ev.metadata.get("page_images_b64", [])
        assert len(page_images) >= 1, "Scanned PDF should have at least 1 extracted page image"

        # Validate the image data
        first_page = page_images[0]
        assert first_page["page_number"] == 1
        assert first_page["mime_type"] == "image/png"
        decoded = base64.b64decode(first_page["image_b64"])
        assert len(decoded) > 100

    def test_multipage_scanned_pdf(self) -> None:
        """Test multi-page scanned PDF."""
        pdf_path = FIXTURE_DIR / "multipage_scanned_invoice.pdf"
        if not pdf_path.exists():
            pytest.skip("Day 17 fixtures not generated")

        adapter = PDFDocumentAdapter()
        result = adapter.ingest_file(pdf_path)

        assert result.status.value == "SUCCESS"
        ev = result.evidence_items[0]
        assert ev.metadata.get("is_scanned") is True
        assert ev.metadata.get("page_count") == 2

    def test_text_pdf_no_page_images(self) -> None:
        """Text PDFs should NOT have page_images_b64."""
        adapter = PDFDocumentAdapter()

        # Create a text-based PDF
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        buf = io.BytesIO()
        writer.write(buf)
        pdf_bytes = buf.getvalue()

        result = adapter.ingest_payload(pdf_bytes, source_name="text_doc.pdf")
        assert result.status.value == "SUCCESS"
        ev = result.evidence_items[0]
        # Text PDF should not have page images
        assert "page_images_b64" not in ev.metadata or ev.metadata.get("page_images_b64") == []


# ============================================================
# A. MOCK PROVIDER — IMAGE AND PDF EVIDENCE
# ============================================================

class TestMockProviderMultimodal:
    """Test AI mock provider with image and PDF evidence."""

    def test_mock_provider_recognizes_image_evidence(self) -> None:
        config = AIProviderConfig(provider_type=AIProviderType.MOCK)
        provider = AIExtractionProvider(config=config)

        ev = Evidence(
            id="EVID-IMG-TEST",
            modality=EvidenceModality.PAYMENT_SCREENSHOT,
            source_type=EvidenceSourceType.MANUAL_UPLOAD,
            source_name="payment.png",
            raw_payload="[IMAGE_ARTIFACT: payment.png | Format: PNG | 400x600px]",
            metadata={
                "image_bytes_b64": base64.b64encode(b"fake_image_data_for_mock").decode(),
                "mime_type": "image/png",
            },
        )

        result = provider.extract(ev)
        assert result.status == ExtractionStatus.SUCCESS
        assert len(result.claims) >= 1
        # Mock should not fabricate specific amounts for image evidence
        claim = result.claims[0]
        assert claim.evidence_id == "EVID-IMG-TEST"

    def test_mock_provider_recognizes_scanned_pdf(self) -> None:
        config = AIProviderConfig(provider_type=AIProviderType.MOCK)
        provider = AIExtractionProvider(config=config)

        ev = Evidence(
            id="EVID-PDF-SCAN-TEST",
            modality=EvidenceModality.INVOICE,
            source_type=EvidenceSourceType.MANUAL_UPLOAD,
            source_name="scanned.pdf",
            raw_payload="[SCANNED_PDF_DOCUMENT: scanned.pdf | Pages: 1]",
            metadata={
                "is_scanned": True,
                "page_images_b64": [{"page_number": 1, "image_b64": "fake", "mime_type": "image/png"}],
            },
        )

        result = provider.extract(ev)
        assert result.status == ExtractionStatus.SUCCESS
        assert len(result.claims) >= 1

    def test_mock_provider_schema_validation(self) -> None:
        """Ensure mock responses pass Pydantic schema validation."""
        config = AIProviderConfig(provider_type=AIProviderType.MOCK)
        provider = AIExtractionProvider(config=config)

        ev = _make_text_evidence("I sent the money")
        result = provider.extract(ev)
        assert result.status == ExtractionStatus.SUCCESS
        # All claims should have valid structure
        for claim in result.claims:
            assert claim.evidence_id == ev.id
            assert isinstance(claim.claim_type, ClaimType)
            assert 0.0 <= claim.confidence <= 1.0


# ============================================================
# A. RELATIVE DATE RESOLUTION
# ============================================================

class TestRelativeDateResolution:
    """Test relative date resolution in TextClaimExtractor."""

    def setup_method(self) -> None:
        self.extractor = TextClaimExtractor()

    def test_yesterday_with_reference(self) -> None:
        ev = _make_text_evidence("payment done 15k yesterday ref 92837")
        ref_date = date(2026, 8, 24)
        result = self.extractor.extract(ev, context={"reference_timestamp": ref_date})
        assert result.status == ExtractionStatus.SUCCESS
        claim = result.claims[0]
        assert claim.claimed_date == "2026-08-23"

    def test_yesterday_without_reference(self) -> None:
        ev = _make_text_evidence("payment done 15k yesterday ref 92837")
        result = self.extractor.extract(ev)
        assert result.status == ExtractionStatus.SUCCESS
        claim = result.claims[0]
        assert "yesterday" in claim.claimed_date
        assert "date_uncertain" in claim.claimed_date

    def test_kal_with_reference(self) -> None:
        ev = _make_text_evidence("bhai maine kal 20k bhej diya usko")
        ref_date = date(2026, 8, 24)
        result = self.extractor.extract(ev, context={"reference_timestamp": ref_date})
        assert result.status == ExtractionStatus.SUCCESS
        claim = result.claims[0]
        assert claim.claimed_date == "2026-08-23"

    def test_tuesday_with_reference(self) -> None:
        ev = _make_text_evidence("Rahul bhai ko 20 hazar UPI kiya tha Tuesday")
        ref_date = date(2026, 8, 24)  # This is a Monday
        result = self.extractor.extract(ev, context={"reference_timestamp": ref_date})
        assert result.status == ExtractionStatus.SUCCESS
        claim = result.claims[0]
        # Should resolve to most recent Tuesday before 2026-08-24 (Monday)
        # Monday(0) - Tuesday(1) = -1 % 7 = 6 days back = Aug 18
        assert claim.claimed_date == "2026-08-18"

    def test_today_with_reference(self) -> None:
        ev = _make_text_evidence("Sent 30k to Vikram via NEFT today ref NEFTN26235889012")
        ref_date = date(2026, 8, 24)
        result = self.extractor.extract(ev, context={"reference_timestamp": ref_date})
        assert result.status == ExtractionStatus.SUCCESS
        claim = result.claims[0]
        assert claim.claimed_date == "2026-08-24"

    def test_parso_with_reference(self) -> None:
        ev = _make_text_evidence("parso 10k bhej diya tha UPI se")
        ref_date = date(2026, 8, 24)
        result = self.extractor.extract(ev, context={"reference_timestamp": ref_date})
        assert result.status == ExtractionStatus.SUCCESS
        claim = result.claims[0]
        assert claim.claimed_date == "2026-08-22"  # 2 days before


# ============================================================
# A. ENHANCED HINGLISH EXTRACTION
# ============================================================

class TestHinglishExtraction:
    """Test expanded Hinglish text extraction."""

    def setup_method(self) -> None:
        self.extractor = TextClaimExtractor()

    def test_bhej_diya_20k(self) -> None:
        ev = _make_text_evidence("bhai maine kal 20k bhej diya usko")
        result = self.extractor.extract(ev)
        assert result.status == ExtractionStatus.SUCCESS
        assert result.claims[0].claimed_amount == 20000.0
        assert result.claims[0].claim_type == ClaimType.PAYMENT_SENT

    def test_upi_kiya_hazar(self) -> None:
        ev = _make_text_evidence("Rahul bhai ko 20 hazar UPI kiya tha Tuesday")
        result = self.extractor.extract(ev)
        assert result.status == ExtractionStatus.SUCCESS
        assert result.claims[0].claimed_amount == 20000.0
        assert result.claims[0].payment_method_hint == "UPI"

    def test_paise_transfer_no_amount(self) -> None:
        ev = _make_text_evidence("paise transfer ho gaye")
        result = self.extractor.extract(ev)
        # 'paise' and 'transfer' are financial indicators but no amount
        assert result.status == ExtractionStatus.SUCCESS
        assert result.claims[0].claimed_amount is None  # Must NOT fabricate

    def test_refund_query(self) -> None:
        ev = _make_text_evidence("refund aa gaya kya? 5k wala")
        result = self.extractor.extract(ev)
        assert result.status == ExtractionStatus.SUCCESS
        assert result.claims[0].claimed_amount == 5000.0

    def test_non_financial_hinglish(self) -> None:
        ev = _make_text_evidence("Good morning bhai! Kaise ho? Office mein milte hain.")
        result = self.extractor.extract(ev)
        assert result.status == ExtractionStatus.NO_CLAIMS_FOUND


# ============================================================
# A. SCHEMA VALIDATION AND HALLUCINATION REJECTION
# ============================================================

class TestSchemaValidationAndSafety:
    """Test AI output schema validation and hallucination rejection."""

    def test_malformed_json_rejected(self) -> None:
        provider = AIExtractionProvider(
            config=AIProviderConfig(provider_type=AIProviderType.MOCK),
            mock_invoker=lambda _: "NOT VALID JSON {{{"
        )
        ev = _make_text_evidence("test")
        result = provider.extract(ev)
        assert result.status == ExtractionStatus.EXTRACTION_ERROR
        assert len(result.claims) == 0

    def test_invalid_claim_type_rejected(self) -> None:
        provider = AIExtractionProvider(
            config=AIProviderConfig(provider_type=AIProviderType.MOCK),
            mock_invoker=lambda _: json.dumps({
                "claims": [{"claim_type": "INVALID_TYPE", "amount": 1000}],
                "is_financial_evidence": True,
            })
        )
        ev = _make_text_evidence("test")
        result = provider.extract(ev)
        assert result.status == ExtractionStatus.EXTRACTION_ERROR

    def test_negative_amount_rejected(self) -> None:
        provider = AIExtractionProvider(
            config=AIProviderConfig(provider_type=AIProviderType.MOCK),
            mock_invoker=lambda _: json.dumps({
                "claims": [{"claim_type": "PAYMENT_SENT", "amount": -5000, "confidence": 0.9}],
                "is_financial_evidence": True,
            })
        )
        ev = _make_text_evidence("test")
        result = provider.extract(ev)
        # Negative amount should fail at Claim construction, caught as EXTRACTION_ERROR
        assert result.status == ExtractionStatus.EXTRACTION_ERROR
        assert len(result.claims) == 0

    def test_confidence_out_of_range_rejected(self) -> None:
        provider = AIExtractionProvider(
            config=AIProviderConfig(provider_type=AIProviderType.MOCK),
            mock_invoker=lambda _: json.dumps({
                "claims": [{"claim_type": "PAYMENT_SENT", "amount": 1000, "confidence": 1.5}],
                "is_financial_evidence": True,
            })
        )
        ev = _make_text_evidence("test")
        result = provider.extract(ev)
        assert result.status == ExtractionStatus.EXTRACTION_ERROR

    def test_null_amount_preserved_not_hallucinated(self) -> None:
        """When evidence says 'sent the money' with no amount, amount must be null."""
        provider = AIExtractionProvider(
            config=AIProviderConfig(provider_type=AIProviderType.MOCK),
            mock_invoker=lambda _: json.dumps({
                "claims": [{
                    "claim_type": "PAYMENT_SENT",
                    "amount": None,
                    "confidence": 0.6,
                    "reasoning": "Payment intent without explicit amount."
                }],
                "is_financial_evidence": True,
            })
        )
        ev = _make_text_evidence("I sent the money")
        result = provider.extract(ev)
        assert result.status == ExtractionStatus.SUCCESS
        assert result.claims[0].claimed_amount is None

    def test_provider_unavailable_without_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("VERITY_AI_API_KEY", raising=False)
        config = AIProviderConfig(
            provider_type=AIProviderType.GEMINI,
            api_key_env_var="GEMINI_API_KEY",
            model_name="gemini-3.6-flash",
        )
        provider = AIExtractionProvider(config=config)
        ev = _make_text_evidence("test payment 5k")
        result = provider.extract(ev)
        assert result.status == ExtractionStatus.PROVIDER_UNAVAILABLE

    def test_config_default_model_name(self) -> None:
        from backend.config import Settings
        s = Settings()
        assert s.ai_model_name == "gemini-3.6-flash"
        assert s.ai_provider_type == "MOCK"


# ============================================================
# A. PROVENANCE PRESERVATION
# ============================================================

class TestProvenancePreservation:
    """Every extracted claim must link back to source evidence."""

    def test_text_claim_provenance(self) -> None:
        extractor = TextClaimExtractor()
        ev = _make_text_evidence("payment done 15k yesterday ref 92837", ev_id="EVID-PROV-001")
        result = extractor.extract(ev)
        assert result.evidence_id == "EVID-PROV-001"
        for claim in result.claims:
            assert claim.evidence_id == "EVID-PROV-001"

    def test_ai_claim_provenance(self) -> None:
        provider = AIExtractionProvider(
            config=AIProviderConfig(provider_type=AIProviderType.MOCK),
            mock_invoker=lambda _: json.dumps({
                "claims": [{"claim_type": "PAYMENT_SENT", "amount": 5000, "confidence": 0.9}],
                "is_financial_evidence": True,
            })
        )
        ev = _make_text_evidence("sent 5k", ev_id="EVID-PROV-002")
        result = provider.extract(ev)
        for claim in result.claims:
            assert claim.evidence_id == "EVID-PROV-002"


# ============================================================
# A. EXTRACTION SERVICE INTEGRATION
# ============================================================

class TestExtractionServiceIntegration:
    """Test ExtractionService routing with image/PDF evidence."""

    def test_image_evidence_routes_to_ai(self) -> None:
        service = ExtractionService()
        ev = Evidence(
            id="EVID-SVC-IMG",
            modality=EvidenceModality.PAYMENT_SCREENSHOT,
            source_type=EvidenceSourceType.MANUAL_UPLOAD,
            source_name="screenshot.png",
            raw_payload="[IMAGE_ARTIFACT: screenshot.png]",
            metadata={
                "image_bytes_b64": base64.b64encode(b"test").decode(),
                "mime_type": "image/png",
            },
        )
        result = service.extract_from_evidence(ev, use_ai_fallback=True)
        # Mock AI should handle this
        assert result.status == ExtractionStatus.SUCCESS

    def test_scanned_pdf_routes_to_ai(self) -> None:
        service = ExtractionService()
        ev = Evidence(
            id="EVID-SVC-PDF",
            modality=EvidenceModality.INVOICE,
            source_type=EvidenceSourceType.MANUAL_UPLOAD,
            source_name="scanned.pdf",
            raw_payload="[SCANNED_PDF_DOCUMENT: scanned.pdf | Pages: 1]",
            metadata={
                "is_scanned": True,
                "page_images_b64": [{"page_number": 1, "image_b64": "fake", "mime_type": "image/png"}],
            },
        )
        result = service.extract_from_evidence(ev, use_ai_fallback=True)
        # Should route through PDF extractor → REQUIRES_VISION → AI fallback
        assert result.status in (ExtractionStatus.SUCCESS, ExtractionStatus.REQUIRES_VISION_OR_OCR)

    def test_text_evidence_deterministic_first(self) -> None:
        service = ExtractionService()
        ev = _make_text_evidence("payment done 15k via UPI ref 92837")
        result = service.extract_from_evidence(ev)
        assert result.status == ExtractionStatus.SUCCESS
        assert result.provider_name == "deterministic_text"


# ============================================================
# B. FULL PIPELINE INTEGRATION — MESSY EVIDENCE → TRUTH
# ============================================================

class TestPipelineIntegration:
    """End-to-end: messy evidence → extraction → deterministic pipeline → truth."""

    def test_messy_text_through_full_pipeline(self) -> None:
        """Messy Hinglish text → claims → entity resolution → matching → reconciliation → truth."""
        from backend.case_processing.models import CaseInput
        from backend.case_processing.pipeline import FinanceControllerPipeline

        # Create a case with messy evidence and a matching transaction
        pipeline = FinanceControllerPipeline()
        case_input = CaseInput(
            case_id="CASE-D17-INTEGRATION",
            evidence_items=[
                Evidence(
                    id="EVID-D17-INT-001",
                    modality=EvidenceModality.MESSAGING_CHAT,
                    source_type=EvidenceSourceType.WHATSAPP_EXPORT,
                    source_name="chat.txt",
                    raw_payload="payment done 15k via UPI ref 408219381920",
                    language_hint="en",
                    metadata={},
                ),
            ],
            transactions=[
                Transaction(
                    id="TXN-D17-INT-001",
                    amount=15000.0,
                    currency="INR",
                    direction="DEBIT",
                    date="2026-08-23",
                    description="UPI/408219381920",
                    source="HDFC_Bank",
                    reference_id="408219381920",
                ),
            ],
            entities=[
                Entity(
                    id="ENT-D17-INT-001",
                    canonical_name="Test Vendor",
                    aliases=["Test"],
                ),
            ],
        )

        result = pipeline.execute(case_input)

        # The pipeline should complete all 8 stages
        assert result.case_id == "CASE-D17-INTEGRATION"
        assert len(result.stage_records) == 8
        assert result.financial_summary["claims_count"] >= 1

        # The AI extraction layer must NOT produce the final financial verdict
        # Verdict comes from deterministic reconciliation
        assert result.status in (
            "CONFIRMED", "PARTIALLY_SETTLED", "UNVERIFIABLE",
            "CONTRADICTED", "AMBIGUOUS", "UNMATCHED",
        )

    def test_ai_does_not_determine_truth(self) -> None:
        """Verify: AI-extracted claims go through deterministic pipeline, not directly to verdict."""
        from backend.case_processing.models import CaseInput
        from backend.case_processing.pipeline import FinanceControllerPipeline

        pipeline = FinanceControllerPipeline()
        case_input = CaseInput(
            case_id="CASE-D17-AI-TRUTH",
            evidence_items=[
                Evidence(
                    id="EVID-D17-AI-001",
                    modality=EvidenceModality.MESSAGING_CHAT,
                    source_type=EvidenceSourceType.WHATSAPP_EXPORT,
                    source_name="chat.txt",
                    raw_payload="I sent the money",
                    metadata={},
                ),
            ],
        )

        result = pipeline.execute(case_input)
        # Without matching transactions, status should NOT be CONFIRMED
        assert result.status != "CONFIRMED"
