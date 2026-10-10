"""Unit tests for Case retrieval, Financial Truth Report, and Provenance DAG endpoints."""

import pytest
from fastapi.testclient import TestClient
from backend.api.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_get_case_report_and_provenance(client: TestClient) -> None:
    # 1. Run demo case to populate in-memory store
    run_resp = client.post("/api/v1/demo-cases/DAY10-01-CLEAN-1TO1/run")
    assert run_resp.status_code == 200

    # 2. Get Case by ID
    get_resp = client.get("/api/v1/cases/DAY10-01-CLEAN-1TO1")
    assert get_resp.status_code == 200
    case_data = get_resp.json()
    assert case_data["case_id"] == "DAY10-01-CLEAN-1TO1"
    assert case_data["status"] == "CONFIRMED"

    # 3. Get Report JSON
    report_resp = client.get("/api/v1/cases/DAY10-01-CLEAN-1TO1/report")
    assert report_resp.status_code == 200
    rep_data = report_resp.json()
    assert rep_data["case_id"] == "DAY10-01-CLEAN-1TO1"
    assert rep_data["status"] == "CONFIRMED"

    # 4. Get Provenance DAG
    prov_resp = client.get("/api/v1/cases/DAY10-01-CLEAN-1TO1/provenance")
    assert prov_resp.status_code == 200
    prov_data = prov_resp.json()
    assert prov_data["case_id"] == "DAY10-01-CLEAN-1TO1"
    assert prov_data["total_nodes"] > 0


def test_get_case_not_found(client: TestClient) -> None:
    get_resp = client.get("/api/v1/cases/NON-EXISTENT-CASE")
    assert get_resp.status_code == 404
