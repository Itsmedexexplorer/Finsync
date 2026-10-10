"""Unit tests for Health and System Info API endpoints."""

import pytest
from fastapi.testclient import TestClient
from backend.api.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "verity"
    assert "day" in data["version"]


def test_info_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/info")
    assert response.status_code == 200
    data = response.json()
    assert "VERITY" in data["app_name"]
    assert "AI Finance Controller" in data["track"]
    assert len(data["available_pipeline_stages"]) == 8
    assert "INGESTION" in data["available_pipeline_stages"]
    assert "REPORTING" in data["available_pipeline_stages"]
