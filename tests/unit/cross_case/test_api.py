"""Unit tests for Day 18 Cross-Case Intelligence API Endpoints."""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.dependencies import get_cross_case_service
from backend.case_processing.service import CaseProcessingService
from backend.storage.service import get_storage_service


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_cross_case_endpoints_workflow(client):
    storage = get_storage_service()
    case_service = CaseProcessingService()

    # 1. Process and persist case
    case_data = {
        "case_id": "API-CROSS-01",
        "evidence": [
            {
                "id": "EV-API-1",
                "modality": "INVOICE",
                "source_name": "inv_api.txt",
                "source_type": "MANUAL_UPLOAD",
                "raw_payload": "INVOICE #API-101 Vendor: Nexus Retail Amount: INR 40,000",
            },
            {
                "id": "EV-API-2",
                "modality": "BANK_STATEMENT",
                "source_name": "bank_api.csv",
                "source_type": "BANK_CSV",
                "raw_payload": "Credit 40000 UTR-NEXUS-01",
            }
        ],
        "claims": [
            {
                "id": "CLM-API-1",
                "evidence_id": "EV-API-1",
                "claim_type": "INVOICE_ISSUED",
                "claimed_amount": 40000.0,
                "reference_id_hint": "UTR-NEXUS-01",
                "counterparty_hint": "Nexus Retail",
            }
        ],
        "transactions": [
            {
                "id": "TXN-API-1",
                "amount": 40000.0,
                "direction": "CREDIT",
                "bank_reference": "UTR-NEXUS-01",
                "evidence_ids": ["EV-API-2"],
            }
        ],
        "entities": [
            {"id": "ENT-NEXUS-1", "canonical_name": "Nexus Retail"}
        ],
    }
    res = case_service.process_benchmark_case(case_data)
    storage.process_and_persist_case(
        case_result=res,
        raw_evidence_list=case_data["evidence"],
        raw_claims_list=case_data["claims"],
        raw_entities_list=case_data["entities"],
        raw_transactions_list=case_data["transactions"],
    )

    # 2. Test GET /api/v1/entities/{id}/history
    r = client.get("/api/v1/entities/Nexus Retail/history")
    assert r.status_code == 200
    hist = r.json()
    assert hist["canonical_name"] == "Nexus Retail"
    assert hist["case_count"] >= 1
    assert hist["total_exposure"] >= 40000.0

    # 3. Test GET /api/v1/entities/{id}/exposure
    r = client.get("/api/v1/entities/Nexus Retail/exposure")
    assert r.status_code == 200
    exp = r.json()
    assert exp["total_exposure"] >= 40000.0

    # 4. Test GET /api/v1/references/{id}/history
    r = client.get("/api/v1/references/UTR-NEXUS-01/history")
    assert r.status_code == 200
    ref_h = r.json()
    assert ref_h["reference_id"] == "UTR-NEXUS-01"
    assert len(ref_h["transaction_ids"]) >= 1

    # 5. Test GET /api/v1/cases/{id}/correlations
    r = client.get("/api/v1/cases/API-CROSS-01/correlations")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # 6. Test GET /api/v1/cases/{id}/historical-signals
    r = client.get("/api/v1/cases/API-CROSS-01/historical-signals")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # 7. Test GET /api/v1/cases/{id}/intelligence-profile
    r = client.get("/api/v1/cases/API-CROSS-01/intelligence-profile")
    assert r.status_code == 200
    prof = r.json()
    assert prof["case_id"] == "API-CROSS-01"
    assert "counterparty_histories" in prof
    assert "reference_correlations" in prof
