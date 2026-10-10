"""Unit tests for Portfolio REST API Endpoints."""

import pytest
from fastapi.testclient import TestClient
from backend.api.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_portfolio_endpoints(client: TestClient) -> None:
    # 1. Seed store by running demo cases
    r1 = client.post("/api/v1/demo-cases/DAY10-01-CLEAN-1TO1/run")
    assert r1.status_code == 200

    r2 = client.post("/api/v1/demo-cases/DAY10-03-AMOUNT-CONTRADICTION/run")
    assert r2.status_code == 200

    # 2. GET /portfolio
    port_resp = client.get("/api/v1/portfolio")
    assert port_resp.status_code == 200
    page_data = port_resp.json()
    assert page_data["total"] >= 2
    assert len(page_data["items"]) >= 2

    # 3. GET /portfolio/summary
    sum_resp = client.get("/api/v1/portfolio/summary")
    assert sum_resp.status_code == 200
    sum_data = sum_resp.json()
    assert sum_data["total_cases"] >= 2

    # 4. GET /portfolio/exposure
    exp_resp = client.get("/api/v1/portfolio/exposure")
    assert exp_resp.status_code == 200
    assert exp_resp.json()["total_exposure"] > 0

    # 5. GET /portfolio/cases/{id}
    case_resp = client.get("/api/v1/portfolio/cases/DAY10-01-CLEAN-1TO1")
    assert case_resp.status_code == 200
    assert case_resp.json()["case_id"] == "DAY10-01-CLEAN-1TO1"

    # 6. POST /portfolio/cases/{id}/assign
    asg_resp = client.post(
        "/api/v1/portfolio/cases/DAY10-01-CLEAN-1TO1/assign",
        json={"reviewer_id": "ctrl_api_test", "reviewer_name": "API Tester"},
    )
    assert asg_resp.status_code == 200
    assert asg_resp.json()["assigned_reviewer_id"] == "ctrl_api_test"

    # 7. GET /portfolio/workload
    work_resp = client.get("/api/v1/portfolio/workload")
    assert work_resp.status_code == 200
    workloads = work_resp.json()
    assert any(w["reviewer_id"] == "ctrl_api_test" for w in workloads)

    # 8. GET /portfolio/review-queue
    rq_resp = client.get("/api/v1/portfolio/review-queue")
    assert rq_resp.status_code == 200

    # 9. GET /portfolio/overdue
    od_resp = client.get("/api/v1/portfolio/overdue")
    assert od_resp.status_code == 200

    # 10. GET /portfolio/high-risk
    hr_resp = client.get("/api/v1/portfolio/high-risk")
    assert hr_resp.status_code == 200
