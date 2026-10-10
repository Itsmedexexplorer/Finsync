"""Unit tests for ExtractionService end-to-end routing, batch processing, and invariants."""

from pathlib import Path
import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.transaction import Transaction
from backend.domain.reconciliation import ReconciliationRecord
from backend.extraction.result import ExtractionStatus
from backend.extraction.service import ExtractionService
from backend.ingestion.service import IngestionService


@pytest.fixture
def extraction_service() -> ExtractionService:
    return ExtractionService()


def test_extraction_service_routes_bank_csv_deterministically(extraction_service: ExtractionService) -> None:
    ev = Evidence(
        id="EVID-CSV-ROUTE-01",
        modality=EvidenceModality.BANK_STATEMENT,
        source_type=EvidenceSourceType.BANK_CSV,
        source_name="stmt.csv:Row2",
        raw_payload="15/08/2026,UPI/408219381920/PAYTO/ROHIT,35000.00,0.00,100000.00",
        metadata={
            "normalized_fields": {
                "date": "15/08/2026",
                "narration": "UPI/408219381920/PAYTO/ROHIT",
                "credit": "35000.00",
                "reference": "408219381920",
            }
        }
    )

    res = extraction_service.extract_from_evidence(ev)
    assert res.status == ExtractionStatus.SUCCESS
    assert res.provider_name == "deterministic_bank_csv"
    assert len(res.claims) == 1
    assert res.claims[0].claimed_amount == 35000.0
    assert res.claims[0].evidence_id == "EVID-CSV-ROUTE-01"


def test_extraction_service_routes_text_message(extraction_service: ExtractionService) -> None:
    ev = Evidence(
        id="EVID-TXT-ROUTE-01",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="chat.txt",
        raw_payload="Bhai 20k GPay kar diya check kar lo",
    )

    res = extraction_service.extract_from_evidence(ev)
    assert res.status == ExtractionStatus.SUCCESS
    assert res.provider_name == "deterministic_text"
    assert len(res.claims) == 1
    assert res.claims[0].claimed_amount == 20000.0
    assert res.claims[0].evidence_id == "EVID-TXT-ROUTE-01"


def test_extraction_service_batch_and_provenance(extraction_service: ExtractionService) -> None:
    evidence_list = [
        Evidence(
            id="EVID-BATCH-1",
            modality=EvidenceModality.MESSAGING_CHAT,
            source_type=EvidenceSourceType.WHATSAPP_EXPORT,
            source_name="chat1.txt",
            raw_payload="Payment of ₹18,500 received from Rahul",
        ),
        Evidence(
            id="EVID-BATCH-2",
            modality=EvidenceModality.MESSAGING_CHAT,
            source_type=EvidenceSourceType.WHATSAPP_EXPORT,
            source_name="chat2.txt",
            raw_payload="I sent the money.",
        ),
    ]

    results = extraction_service.extract_from_evidence_batch(evidence_list)
    assert len(results) == 2

    # Verify provenance on every claim
    for idx, res in enumerate(results):
        assert res.evidence_id == evidence_list[idx].id
        for c in res.claims:
            assert c.evidence_id == evidence_list[idx].id


def test_extraction_service_invariant_claims_only(extraction_service: ExtractionService) -> None:
    """Invariant test: Extraction layer creates Claims ONLY, never Transactions or Reconciliations."""
    ev = Evidence(
        id="EVID-INV-CHECK",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="chat.txt",
        raw_payload="Bhai 50k GPay kar diya",
    )

    result = extraction_service.extract_from_evidence(ev)
    assert result.status == ExtractionStatus.SUCCESS
    
    for c in result.claims:
        assert isinstance(c, Claim)
        assert not isinstance(c, Transaction)
        assert not isinstance(c, ReconciliationRecord)


def test_extraction_service_on_ingested_day2_samples(extraction_service: ExtractionService) -> None:
    """End-to-end verification: Ingestion -> Evidence -> Extraction -> Claims."""
    ingestion_service = IngestionService()
    samples_dir = Path("data/samples/day2")
    ing_res = ingestion_service.ingest_batch(samples_dir)
    assert len(ing_res.evidence_items) >= 10

    ext_results = extraction_service.extract_from_evidence_batch(ing_res.evidence_items)
    assert len(ext_results) == len(ing_res.evidence_items)
    
    total_claims = sum(len(r.claims) for r in ext_results)
    assert total_claims >= 10
