"""Unit tests for defensive security headers and CORS policies."""

import pytest
from fastapi.testclient import TestClient
from backend.api.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_security_headers_present(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_api_cache_control_header(client: TestClient) -> None:
    response = client.get("/api/v1/info")
    assert response.status_code == 200
    cache_ctrl = response.headers.get("Cache-Control", "")
    assert "no-store" in cache_ctrl or "no-cache" in cache_ctrl


def test_cors_preflight_allowed_origin(client: TestClient) -> None:
    response = client.options(
        "/api/v1/info",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"
