"""Unit tests for unified IngestionService and batch processing."""

from pathlib import Path
import pytest
from PIL import Image

from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.claim import Claim
from backend.domain.transaction import Transaction
from backend.domain.reconciliation import ReconciliationRecord
from backend.ingestion.result import IngestionStatus
from backend.ingestion.service import IngestionService
from scripts.create_day2_samples import generate_minimal_text_pdf


@pytest.fixture
def ingestion_service() -> IngestionService:
    return IngestionService()


def test_ingestion_service_direct_text(ingestion_service: IngestionService) -> None:
    res = ingestion_service.ingest_text("Bhai 20k GPay kar diya check kar lo")
    assert res.status == IngestionStatus.SUCCESS
    assert len(res.evidence_items) == 1
    assert res.evidence_items[0].modality == EvidenceModality.MESSAGING_CHAT


def test_ingestion_service_mixed_batch_directory(ingestion_service: IngestionService, tmp_path: Path) -> None:
    # 1. CSV
    (tmp_path / "bank.csv").write_text("Date,Narration,Amount\n15/08/2026,UPI Transfer,25000.00\n", encoding="utf-8")

    # 2. Text Chat
    (tmp_path / "chat.txt").write_text("[15/08/2026, 12:00] User: Sent payment\n", encoding="utf-8")

    # 3. PDF
    pdf_bytes = generate_minimal_text_pdf(["TAX INVOICE #INV-100", "Amount: Rs. 25000"])
    (tmp_path / "invoice.pdf").write_bytes(pdf_bytes)

    # 4. PNG
    img = Image.new("RGB", (200, 200), color=(200, 200, 200))
    img.save(tmp_path / "screenshot.png", format="PNG")

    # Run batch ingestion on folder
    result = ingestion_service.ingest_batch(tmp_path)
    assert result.status == IngestionStatus.SUCCESS
    assert len(result.evidence_items) == 4
    assert len(result.errors) == 0

    modalities = {ev.modality for ev in result.evidence_items}
    assert EvidenceModality.BANK_STATEMENT in modalities
    assert EvidenceModality.MESSAGING_CHAT in modalities
    assert EvidenceModality.INVOICE in modalities
    assert EvidenceModality.PAYMENT_SCREENSHOT in modalities


def test_ingestion_service_partial_batch_with_invalid_file(ingestion_service: IngestionService, tmp_path: Path) -> None:
    # 1. Valid CSV
    (tmp_path / "valid.csv").write_text("Date,Narration,Amount\n15/08/2026,UPI,1000.00\n", encoding="utf-8")

    # 2. Corrupted PDF
    (tmp_path / "broken.pdf").write_bytes(b"bad pdf bytes")

    result = ingestion_service.ingest_batch(tmp_path)
    assert result.status == IngestionStatus.PARTIAL_SUCCESS
    assert len(result.evidence_items) == 1
    assert len(result.errors) == 1
    assert result.errors[0].source_name == "broken.pdf"


def test_ingestion_service_preserves_invariant_evidence_only(ingestion_service: IngestionService, tmp_path: Path) -> None:
    """Invariant test: Ingestion layer produces Evidence objects ONLY, never Claims or Reconciliations."""
    csv_file = tmp_path / "stmt.csv"
    csv_file.write_text("Date,Narration,Amount\n15/08/2026,UPI/408219381920/PAYTO,15000.00\n", encoding="utf-8")

    result = ingestion_service.ingest_file(csv_file)
    assert result.status == IngestionStatus.SUCCESS
    
    for item in result.evidence_items:
        # Strictly an Evidence instance
        assert isinstance(item, Evidence)
        assert not isinstance(item, Claim)
        assert not isinstance(item, Transaction)
        assert not isinstance(item, ReconciliationRecord)


def test_ingestion_service_sample_day2_directory(ingestion_service: IngestionService) -> None:
    """Ingest the realistic sample files generated in data/samples/day2."""
    samples_dir = Path("data/samples/day2")
    assert samples_dir.exists()

    result = ingestion_service.ingest_batch(samples_dir)
    assert result.status in (IngestionStatus.SUCCESS, IngestionStatus.PARTIAL_SUCCESS)
    assert len(result.evidence_items) >= 10
    
    # Verify all Evidence items have valid non-empty SHA-256 hashes
    for ev in result.evidence_items:
        assert len(ev.content_hash) == 64
        assert ev.id.startswith("EVID-")
