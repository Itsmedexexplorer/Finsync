"""Unit tests for Health and Readiness diagnostics."""

import pytest
from fastapi.testclient import TestClient
from backend.api.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_liveness(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "verity"


def test_readiness_diagnostics(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["config_valid"] is True
    assert data["case_store_ready"] is True
    assert data["benchmark_available"] is True
    assert data["pipeline_ready"] is True
    assert isinstance(data["active_cases_in_memory"], int)
