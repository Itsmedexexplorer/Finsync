"""Adversarial REST API Security Tests for Day 19 Remediation Endpoints."""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.case_processing.service import CaseProcessingService
from backend.storage.service import get_storage_service


@pytest.fixture
def api_client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def seeded_case(api_client):
    storage = get_storage_service()
    case_service = CaseProcessingService()

    case_data = {
        "case_id": "API-ADV-CASE-01",
        "evidence": [
            {
                "id": "EV-API-1",
                "modality": "INVOICE",
                "source_name": "inv.txt",
                "source_type": "MANUAL_UPLOAD",
                "raw_payload": "INVOICE #INV-API-ADV Vendor: Cyber Security Ltd Amount: INR 75,000",
            },
            {
                "id": "EV-API-2",
                "modality": "BANK_STATEMENT",
                "source_name": "bank.csv",
                "source_type": "BANK_CSV",
                "raw_payload": "Credit 75000 UTR-CYBER-01",
            }
        ],
        "claims": [
            {
                "id": "CLM-API-1",
                "evidence_id": "EV-API-1",
                "claim_type": "INVOICE_ISSUED",
                "claimed_amount": 75000.0,
                "reference_id_hint": "UTR-CYBER-01",
                "counterparty_hint": "Cyber Security Ltd",
            }
        ],
        "transactions": [
            {
                "id": "TXN-API-1",
                "amount": 75000.0,
                "direction": "CREDIT",
                "bank_reference": "UTR-CYBER-01",
                "evidence_ids": ["EV-API-2"],
            }
        ],
        "entities": [{"id": "ENT-API-1", "canonical_name": "Cyber Security Ltd"}],
    }
    res = case_service.process_benchmark_case(case_data)
    storage.process_and_persist_case(
        case_result=res,
        raw_evidence_list=case_data["evidence"],
        raw_claims_list=case_data["claims"],
        raw_entities_list=case_data["entities"],
        raw_transactions_list=case_data["transactions"],
    )
    return "API-ADV-CASE-01"


def _get_err_msg(resp) -> str:
    data = resp.json()
    if "error" in data and isinstance(data["error"], dict):
        return data["error"].get("message", "")
    return data.get("detail", str(data))


def test_api_attack_invalid_action_type(api_client, seeded_case):
    # Proposing an unsupported action type must return 400 Bad Request
    r = api_client.post(
        f"/api/v1/cases/{seeded_case}/actions/propose",
        json={"action_type": "MALICIOUS_EXECUTE_PAYMENT"},
    )
    assert r.status_code == 400
    assert "Unsupported action type" in _get_err_msg(r)


def test_api_attack_nonexistent_case_propose(api_client):
    r = api_client.post(
        "/api/v1/cases/NON_EXISTENT_CASE/actions/propose",
        json={"action_type": "VENDOR_DISPUTE_NOTICE"},
    )
    assert r.status_code == 400
    assert "No reconciliation record found" in _get_err_msg(r)


def test_api_attack_approve_nonexistent_action(api_client, seeded_case):
    r = api_client.post(
        f"/api/v1/cases/{seeded_case}/actions/ACT-FAKE-NONEXISTENT/approve",
        json={"reviewer_id": "ctrl_1"},
    )
    assert r.status_code == 404
    assert "not found" in _get_err_msg(r).lower()


def test_api_attack_approve_empty_reviewer(api_client, seeded_case):
    # First propose valid action
    prop_res = api_client.post(
        f"/api/v1/cases/{seeded_case}/actions/propose",
        json={"action_type": "PAYMENT_FOLLOWUP_DRAFT"},
    )
    assert prop_res.status_code == 200
    action_id = prop_res.json()["action_id"]

    # Attempt approval with empty reviewer_id
    r = api_client.post(
        f"/api/v1/cases/{seeded_case}/actions/{action_id}/approve",
        json={"reviewer_id": "   "},
    )
    assert r.status_code == 400
    assert "Reviewer ID is required" in _get_err_msg(r)


def test_api_attack_replay_approval(api_client, seeded_case):
    # Propose valid action
    prop_res = api_client.post(
        f"/api/v1/cases/{seeded_case}/actions/propose",
        json={"action_type": "PAYMENT_FOLLOWUP_DRAFT"},
    )
    action_id = prop_res.json()["action_id"]

    # 1st approval succeeds
    r1 = api_client.post(
        f"/api/v1/cases/{seeded_case}/actions/{action_id}/approve",
        json={"reviewer_id": "controller_alice"},
    )
    assert r1.status_code == 200

    # 2nd approval (replay attack) fails with 400 Bad Request
    r2 = api_client.post(
        f"/api/v1/cases/{seeded_case}/actions/{action_id}/approve",
        json={"reviewer_id": "controller_bob"},
    )
    assert r2.status_code == 400
    assert "Cannot approve" in _get_err_msg(r2)


def test_api_attack_approve_rejected_action(api_client, seeded_case):
    # Propose valid action
    prop_res = api_client.post(
        f"/api/v1/cases/{seeded_case}/actions/propose",
        json={"action_type": "MISSING_EVIDENCE_REQUEST"},
    )
    action_id = prop_res.json()["action_id"]

    # Reject action
    rej = api_client.post(
        f"/api/v1/cases/{seeded_case}/actions/{action_id}/reject",
        json={"reviewer_id": "controller_alice", "reason": "No evidence needed"},
    )
    assert rej.status_code == 200
    assert rej.json()["approval_status"] == "REJECTED"

    # Attempt to approve rejected action fails with 400 Bad Request
    app_res = api_client.post(
        f"/api/v1/cases/{seeded_case}/actions/{action_id}/approve",
        json={"reviewer_id": "controller_alice"},
    )
    assert app_res.status_code == 400
    assert "Cannot approve" in _get_err_msg(app_res)


def test_api_attack_nonexistent_journal_voucher(api_client):
    r = api_client.get("/api/v1/cases/NON_EXISTENT_CASE/journal-voucher")
    assert r.status_code == 404
