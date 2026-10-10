"""Unit tests for clean 1:1 case processing."""

import pytest
from backend.case_processing.models import CaseInput
from backend.case_processing.service import CaseProcessingService
from backend.domain.claim import Claim, ClaimType
from backend.domain.entity import Entity, EntityType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.transaction import Transaction, TransactionDirection


@pytest.fixture
def service() -> CaseProcessingService:
    return CaseProcessingService()


def test_clean_case_full_pipeline_execution(service: CaseProcessingService) -> None:
    ev_inv = Evidence(id="E1", modality=EvidenceModality.INVOICE, source_type=EvidenceSourceType.ZOHO_INVOICE, source_name="inv.pdf", raw_payload="35k inv")
    ev_bank = Evidence(id="E2", modality=EvidenceModality.BANK_STATEMENT, source_type=EvidenceSourceType.BANK_CSV, source_name="bank.csv", raw_payload="35k bank")
    
    claim = Claim(id="C1", evidence_id="E1", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=35000.0, reference_id_hint="408219381920", counterparty_hint="Rahul Kumar")
    txn = Transaction(id="T1", amount=35000.0, direction=TransactionDirection.CREDIT, bank_reference="408219381920", origin_entity_id="ENT-001", evidence_ids=["E2"])
    entity = Entity(id="ENT-001", canonical_name="Rahul Kumar", entity_type=EntityType.INDIVIDUAL, pan="ABCDE1234F")

    case_in = CaseInput(
        case_id="CASE-CLEAN-01",
        evidence_items=[ev_inv, ev_bank],
        transactions=[txn],
        entities=[entity],
        metadata={"precomputed_claims": [claim.model_dump()]},
    )

    result = service.process_case(case_in)

    assert result.case_id == "CASE-CLEAN-01"
    assert result.status == "CONFIRMED"
    assert result.confidence_score >= 0.95
    assert result.financial_summary["matched_amount"] == 35000.0
    assert result.financial_summary["outstanding_amount"] == 0.0
    assert len(result.stage_records) == 8
    assert result.report is not None
    assert result.report.status.value == "CONFIRMED"
