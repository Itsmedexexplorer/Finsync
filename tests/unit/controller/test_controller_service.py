"""Unit tests for ControllerService end-to-end flow."""

import pytest
from backend.case_processing.service import CaseProcessingService
from backend.controller.models import ControllerActionType, ControllerRiskLevel
from backend.controller.service import ControllerService


@pytest.fixture
def case_service() -> CaseProcessingService:
    return CaseProcessingService()


@pytest.fixture
def controller_service() -> ControllerService:
    return ControllerService()


def test_controller_analyze_clean_case(case_service: CaseProcessingService, controller_service: ControllerService) -> None:
    case_dict = {
        "case_id": "CLEAN-TEST-01",
        "evidence": [
            {
                "id": "E1",
                "modality": "INVOICE",
                "source_type": "ZOHO_INVOICE",
                "source_name": "inv.pdf",
                "raw_payload": "35k inv",
            }
        ],
        "claims": [
            {
                "id": "C1",
                "evidence_id": "E1",
                "claim_type": "INVOICE_ISSUED",
                "claimed_amount": 35000.0,
                "reference_id_hint": "408219381920",
                "counterparty_hint": "Rahul Kumar",
            }
        ],
        "transactions": [
            {
                "id": "T1",
                "amount": 35000.0,
                "direction": "CREDIT",
                "bank_reference": "408219381920",
                "origin_entity_id": "ENT-001",
            }
        ],
        "entities": [
            {
                "id": "ENT-001",
                "canonical_name": "Rahul Kumar",
                "entity_type": "INDIVIDUAL",
                "pan": "ABCDE1234F",
            }
        ],
    }

    result = case_service.process_benchmark_case(case_dict)
    decision = controller_service.analyze_case(result)
    brief = controller_service.build_brief(result)

    assert decision.case_id == "CLEAN-TEST-01"
    assert decision.risk_level == ControllerRiskLevel.NONE
    assert decision.decision == ControllerActionType.CONFIRM_RECONCILIATION
    assert decision.requires_human_review is False
    assert "CONFIRMED" in brief.executive_summary
