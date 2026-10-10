"""Unit tests for Day 19 Remediation and Journal Voucher API routes."""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.case_processing.service import CaseProcessingService
from backend.storage.service import get_storage_service


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_remediation_api_workflow(client):
    storage = get_storage_service()
    case_service = CaseProcessingService()

    case_data = {
        "case_id": "API-REM-01",
        "evidence": [
            {
                "id": "EV-1",
                "modality": "INVOICE",
                "source_name": "inv.txt",
                "source_type": "MANUAL_UPLOAD",
                "raw_payload": "INVOICE #INV-API Vendor: Orion Solutions Amount: INR 50,000",
            },
            {
                "id": "EV-2",
                "modality": "BANK_STATEMENT",
                "source_name": "bank.csv",
                "source_type": "BANK_CSV",
                "raw_payload": "Credit 50000 UTR-ORION-01",
            }
        ],
        "claims": [
            {
                "id": "CLM-1",
                "evidence_id": "EV-1",
                "claim_type": "INVOICE_ISSUED",
                "claimed_amount": 50000.0,
                "reference_id_hint": "UTR-ORION-01",
                "counterparty_hint": "Orion Solutions",
            }
        ],
        "transactions": [
            {
                "id": "TXN-1",
                "amount": 50000.0,
                "direction": "CREDIT",
                "bank_reference": "UTR-ORION-01",
                "evidence_ids": ["EV-2"],
            }
        ],
        "entities": [{"id": "ENT-1", "canonical_name": "Orion Solutions"}],
    }
    res = case_service.process_benchmark_case(case_data)
    storage.process_and_persist_case(
        case_result=res,
        raw_evidence_list=case_data["evidence"],
        raw_claims_list=case_data["claims"],
        raw_entities_list=case_data["entities"],
        raw_transactions_list=case_data["transactions"],
    )

    # 1. Propose action via POST /api/v1/cases/{case_id}/actions/propose
    r = client.post("/api/v1/cases/API-REM-01/actions/propose", json={"action_type": "PAYMENT_FOLLOWUP_DRAFT"})
    assert r.status_code == 200
    action = r.json()
    action_id = action["action_id"]
    assert action["approval_status"] == "PENDING_APPROVAL"

    # 2. List actions via GET /api/v1/cases/{case_id}/actions
    r = client.get("/api/v1/cases/API-REM-01/actions")
    assert r.status_code == 200
    actions = r.json()
    assert len(actions) >= 1

    # 3. Approve action via POST /api/v1/cases/{case_id}/actions/{action_id}/approve
    r = client.post(f"/api/v1/cases/API-REM-01/actions/{action_id}/approve", json={"reviewer_id": "lead_ctrl"})
    assert r.status_code == 200
    approved = r.json()
    assert approved["approval_status"] == "APPROVED"
    assert approved["approved_by"] == "lead_ctrl"

    # 4. Get journal voucher via GET /api/v1/cases/{case_id}/journal-voucher
    r = client.get("/api/v1/cases/API-REM-01/journal-voucher")
    assert r.status_code == 200
    voucher = r.json()
    assert voucher["is_balanced"] is True
    assert voucher["total_debits"] == 50000.0
    assert voucher["total_credits"] == 50000.0

    # 5. Export journal voucher via POST /api/v1/cases/{case_id}/journal-voucher/export
    r = client.post("/api/v1/cases/API-REM-01/journal-voucher/export", json={"format": "JSON"})
    assert r.status_code == 200
    export_resp = r.json()
    assert export_resp["status"] == "EXPORTED"
    assert export_resp["audit_recorded"] is True
