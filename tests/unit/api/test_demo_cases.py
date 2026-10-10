"""Unit tests for Demo Cases API endpoints."""

import pytest
from fastapi.testclient import TestClient
from backend.api.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_list_demo_cases(client: TestClient) -> None:
    response = client.get("/api/v1/demo-cases")
    assert response.status_code == 200
    cases = response.json()
    assert len(cases) == 10
    case_ids = [c["case_id"] for c in cases]
    assert "DAY10-01-CLEAN-1TO1" in case_ids
    assert "DAY10-02-PARTIAL-SETTLEMENT" in case_ids
    assert "DAY10-03-AMOUNT-CONTRADICTION" in case_ids


def test_run_demo_case_clean(client: TestClient) -> None:
    response = client.post("/api/v1/demo-cases/DAY10-01-CLEAN-1TO1/run")
    assert response.status_code == 200
    data = response.json()
    assert data["case_id"] == "DAY10-01-CLEAN-1TO1"
    assert data["status"] == "CONFIRMED"
    assert data["requires_review"] is False
    assert data["financial_summary"]["matched_amount"] == 35000.0
    assert len(data["stage_execution"]) == 8


def test_run_demo_case_not_found(client: TestClient) -> None:
    response = client.post("/api/v1/demo-cases/NON-EXISTENT-CASE/run")
    assert response.status_code == 404
