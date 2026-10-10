"""Unit tests for PDFDocumentAdapter in VERITY Ingestion subsystem."""

from pathlib import Path
import pytest
import pypdf

from backend.domain.evidence import EvidenceModality, EvidenceSourceType
from backend.ingestion.pdf_adapter import PDFDocumentAdapter
from backend.ingestion.result import IngestionStatus
from scripts.create_day2_samples import generate_minimal_text_pdf


@pytest.fixture
def pdf_adapter() -> PDFDocumentAdapter:
    return PDFDocumentAdapter()


def test_pdf_adapter_text_based_invoice(pdf_adapter: PDFDocumentAdapter, tmp_path: Path) -> None:
    pdf_bytes = generate_minimal_text_pdf([
        "TAX INVOICE #INV-2026-999",
        "Billed To: Acme Corp India",
        "Total Amount: Rs. 50,000.00",
    ])
    pdf_file = tmp_path / "invoice_999.pdf"
    pdf_file.write_bytes(pdf_bytes)

    result = pdf_adapter.ingest_file(pdf_file)
    assert result.status == IngestionStatus.SUCCESS
    assert len(result.evidence_items) == 1

    ev = result.evidence_items[0]
    assert ev.modality == EvidenceModality.INVOICE
    assert "TAX INVOICE #INV-2026-999" in ev.raw_payload
    assert ev.metadata["is_scanned"] is False
    assert ev.metadata["page_count"] == 1
    assert len(ev.content_hash) == 64


def test_pdf_adapter_scanned_image_pdf(pdf_adapter: PDFDocumentAdapter, tmp_path: Path) -> None:
    # Create a blank PDF page without any text stream
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=595, height=842)
    scanned_file = tmp_path / "scanned_receipt.pdf"
    with open(scanned_file, "wb") as f:
        writer.write(f)

    result = pdf_adapter.ingest_file(scanned_file)
    assert result.status == IngestionStatus.SUCCESS
    assert len(result.evidence_items) == 1

    ev = result.evidence_items[0]
    assert ev.metadata["is_scanned"] is True
    assert "[SCANNED_PDF_DOCUMENT" in ev.raw_payload
    assert ev.metadata["page_count"] == 1


def test_pdf_adapter_corrupted_pdf(pdf_adapter: PDFDocumentAdapter, tmp_path: Path) -> None:
    corrupted_file = tmp_path / "corrupted.pdf"
    corrupted_file.write_bytes(b"%PDF-1.4\nCorrupted binary garbage without valid xref or objects")

    result = pdf_adapter.ingest_file(corrupted_file)
    assert result.status == IngestionStatus.MALFORMED_DATA
    assert len(result.evidence_items) == 0
    assert len(result.errors) == 1
    assert "corrupted or invalid" in result.errors[0].message.lower()


def test_pdf_adapter_empty_and_nonexistent(pdf_adapter: PDFDocumentAdapter, tmp_path: Path) -> None:
    # 0 bytes file
    empty_file = tmp_path / "empty.pdf"
    empty_file.write_bytes(b"")

    res_empty = pdf_adapter.ingest_file(empty_file)
    assert res_empty.status == IngestionStatus.INVALID_INPUT

    # Non-existent file
    res_missing = pdf_adapter.ingest_file("non_existent_doc.pdf")
    assert res_missing.status == IngestionStatus.INVALID_INPUT
