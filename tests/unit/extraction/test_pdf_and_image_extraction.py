"""Unit tests for PDF and Image claims extraction."""

import pytest
from backend.domain.claim import ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.extraction.pdf_extractor import PDFDocumentExtractor
from backend.extraction.result import ExtractionStatus


@pytest.fixture
def pdf_extractor() -> PDFDocumentExtractor:
    return PDFDocumentExtractor()


def test_pdf_extractor_text_invoice(pdf_extractor: PDFDocumentExtractor) -> None:
    raw_payload = """TAX INVOICE #INV-2026-088
Billed To: Creative Minds Design Studio
Description: UI/UX Retainer Services August 2026
Amount Due: Rs. 35,000.00
Due Date: 2026-08-25"""

    ev = Evidence(
        id="EVID-PDF-001",
        modality=EvidenceModality.INVOICE,
        source_type=EvidenceSourceType.ZOHO_INVOICE,
        source_name="INV-2026-088.pdf",
        raw_payload=raw_payload,
        metadata={"is_scanned": False, "page_count": 1},
    )

    result = pdf_extractor.extract(ev)
    assert result.status == ExtractionStatus.SUCCESS
    assert len(result.claims) == 1

    claim = result.claims[0]
    assert claim.evidence_id == "EVID-PDF-001"
    assert claim.claim_type == ClaimType.INVOICE_ISSUED
    assert claim.claimed_amount == 35000.0
    assert claim.reference_id_hint == "INV-2026-088"
    assert claim.counterparty_hint == "Creative Minds Design Studio"
    assert claim.claimed_date == "2026-08-25"


def test_pdf_extractor_scanned_document_requires_vision(pdf_extractor: PDFDocumentExtractor) -> None:
    ev = Evidence(
        id="EVID-PDF-SCANNED",
        modality=EvidenceModality.INVOICE,
        source_type=EvidenceSourceType.MANUAL_UPLOAD,
        source_name="scanned_paper.pdf",
        raw_payload="[SCANNED_PDF_DOCUMENT: scanned_paper.pdf | Pages: 1 | Size: 45000 bytes]",
        metadata={"is_scanned": True, "page_count": 1},
    )

    result = pdf_extractor.extract(ev)
    assert result.status == ExtractionStatus.REQUIRES_VISION_OR_OCR
    assert len(result.claims) == 0
    assert "requires multimodal vision/ocr" in result.errors[0].lower()
