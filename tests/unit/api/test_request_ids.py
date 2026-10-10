"""Unit tests for Request-ID generation, propagation, and headers."""

import pytest
from fastapi.testclient import TestClient
from backend.api.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_request_id_generated_automatically(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    req_id = response.headers["X-Request-ID"]
    assert req_id.startswith("req-")


def test_incoming_request_id_propagated(client: TestClient) -> None:
    custom_id = "client-trace-abc-12345"
    response = client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_id


def test_request_id_in_error_payload(client: TestClient) -> None:
    custom_id = "trace-error-9999"
    response = client.get("/api/v1/cases/NON-EXISTENT", headers={"X-Request-ID": custom_id})
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["request_id"] == custom_id
    assert response.headers["X-Request-ID"] == custom_id
