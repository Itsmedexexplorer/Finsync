"""Unit tests for Controller API Endpoints."""

import pytest
from fastapi.testclient import TestClient
from backend.api.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_controller_decision_and_brief_endpoints(client: TestClient) -> None:
    # 1. Run a clean demo case
    run_resp = client.post("/api/v1/demo-cases/DAY10-01-CLEAN-1TO1/run")
    assert run_resp.status_code == 200

    # 2. GET /controller decision
    dec_resp = client.get("/api/v1/cases/DAY10-01-CLEAN-1TO1/controller")
    assert dec_resp.status_code == 200
    dec_data = dec_resp.json()
    assert dec_data["case_id"] == "DAY10-01-CLEAN-1TO1"
    assert dec_data["risk_level"] in ("NONE", "LOW")
    assert dec_data["decision"] == "CONFIRM_RECONCILIATION"
    assert dec_data["requires_human_review"] is False

    # 3. GET /controller/brief
    brief_resp = client.get("/api/v1/cases/DAY10-01-CLEAN-1TO1/controller/brief")
    assert brief_resp.status_code == 200
    brief_data = brief_resp.json()
    assert "executive_summary" in brief_data
    assert "risk_summary" in brief_data
    assert len(brief_data["recommended_actions"]) > 0

    # 4. POST /controller/explain
    explain_resp = client.post(
        "/api/v1/cases/DAY10-01-CLEAN-1TO1/controller/explain",
        json={"question": "Why is this case confirmed?"},
    )
    assert explain_resp.status_code == 200
    exp_data = explain_resp.json()
    assert exp_data["case_id"] == "DAY10-01-CLEAN-1TO1"
    assert "clean" in exp_data["answer"].lower() or "confirmed" in exp_data["answer"].lower()


def test_controller_endpoints_case_not_found(client: TestClient) -> None:
    resp = client.get("/api/v1/cases/NON-EXISTENT-CASE/controller")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CASE_NOT_FOUND"
