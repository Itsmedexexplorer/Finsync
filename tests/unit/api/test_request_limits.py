"""Unit tests for request limits, upload sizes, and complexity bounds."""

import pytest
from fastapi.testclient import TestClient
from backend.api.app import app
from backend.config import get_settings


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_text_length_limit_exceeded(client: TestClient) -> None:
    settings = get_settings()
    oversized_text = "A" * (settings.max_text_length + 100)
    
    response = client.post("/api/v1/cases/text", json={"text": oversized_text})
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_INPUT"
    assert "character limit" in data["error"]["message"]


def test_file_size_limit_exceeded(client: TestClient) -> None:
    settings = get_settings()
    # Create fake oversized content in memory exceeding max_upload_bytes
    oversized_bytes = b"0" * (settings.max_upload_bytes + 1024)
    files = [("files", ("oversized_statement.csv", oversized_bytes, "text/csv"))]

    response = client.post("/api/v1/cases/files", files=files)
    assert response.status_code == 413
    data = response.json()
    assert data["error"]["code"] == "FILE_TOO_LARGE"
    assert "maximum allowed size" in data["error"]["message"]


def test_max_files_per_upload_limit_exceeded(client: TestClient) -> None:
    settings = get_settings()
    # Create more files than allowed
    files = [
        ("files", (f"file_{i}.txt", b"text payload", "text/plain"))
        for i in range(settings.max_files_per_case + 2)
    ]
    response = client.post("/api/v1/cases/files", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_INPUT"
    assert "maximum allowed files" in data["error"]["message"]
