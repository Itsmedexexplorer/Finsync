"""Unit tests for structured API error handling and traceback masking."""

import pytest
from fastapi.testclient import TestClient
from backend.api.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_404_structured_error_response(client: TestClient) -> None:
    response = client.get("/api/v1/cases/NON-EXISTENT-CASE-12345")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "CASE_NOT_FOUND"
    assert "request_id" in data["error"]
    assert "NON-EXISTENT-CASE-12345" in data["error"]["message"]


def test_422_validation_error_format(client: TestClient) -> None:
    # Sending malformed body missing required case_id
    response = client.post("/api/v1/cases", json={})
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_INPUT"
    assert "case_id" in data["error"]["message"]
    assert "request_id" in data["error"]


def test_415_unsupported_media_error_format(client: TestClient) -> None:
    files = [("files", ("exploit.exe", b"binary content", "application/x-msdownload"))]
    response = client.post("/api/v1/cases/files", files=files)
    assert response.status_code == 415
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "UNSUPPORTED_MEDIA"
    assert "Supported extensions" in data["error"]["message"]
