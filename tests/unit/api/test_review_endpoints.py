"""Unit tests for Human Review API Endpoints."""

import pytest
from fastapi.testclient import TestClient
from backend.api.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_review_api_lifecycle(client: TestClient) -> None:
    # 1. Run a demo case to seed memory store
    run_resp = client.post("/api/v1/demo-cases/DAY10-01-CLEAN-1TO1/run")
    assert run_resp.status_code == 200

    # 2. GET /review
    rev_resp = client.get("/api/v1/cases/DAY10-01-CLEAN-1TO1/review")
    assert rev_resp.status_code == 200
    rev_data = rev_resp.json()
    assert rev_data["case_id"] == "DAY10-01-CLEAN-1TO1"

    # 3. POST /review/start
    start_resp = client.post(
        "/api/v1/cases/DAY10-01-CLEAN-1TO1/review/start",
        json={"reviewer_id": "ctrl_test", "reviewer_name": "API Tester"},
    )
    assert start_resp.status_code == 200
    assert start_resp.json()["status"] == "IN_PROGRESS"

    # 4. POST /review/note
    note_resp = client.post(
        "/api/v1/cases/DAY10-01-CLEAN-1TO1/review/note",
        json={"content": "Inspection completed via automated test.", "reviewer_id": "ctrl_test"},
    )
    assert note_resp.status_code == 200

    # 5. POST /review/decision
    dec_resp = client.post(
        "/api/v1/cases/DAY10-01-CLEAN-1TO1/review/decision",
        json={"decision": "CONFIRMED", "reviewer_id": "ctrl_test"},
    )
    assert dec_resp.status_code == 200
    assert dec_resp.json()["decision"] == "CONFIRMED"

    # 6. GET /review/audit/verify
    verify_resp = client.get("/api/v1/cases/DAY10-01-CLEAN-1TO1/review/audit/verify")
    assert verify_resp.status_code == 200
    assert verify_resp.json()["is_valid"] is True

    # 7. GET /review/summary
    sum_resp = client.get("/api/v1/cases/DAY10-01-CLEAN-1TO1/review/summary")
    assert sum_resp.status_code == 200
    assert sum_resp.json()["deterministic_status"] == "CONFIRMED"


def test_review_api_case_not_found(client: TestClient) -> None:
    resp = client.get("/api/v1/cases/NON-EXISTENT-CASE/review")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CASE_NOT_FOUND"
