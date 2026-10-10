"""Unit tests for Storage API Endpoints."""

import pytest
from fastapi.testclient import TestClient
from backend.api.app import create_app
from backend.storage.service import get_storage_service, reset_storage_service


@pytest.fixture
def client():
    reset_storage_service()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    reset_storage_service()


def test_storage_health_endpoint(client):
    response = client.get("/api/v1/storage/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert data["dialect"] == "sqlite"


def test_storage_stats_endpoint(client):
    response = client.get("/api/v1/storage/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert "cases" in data["tables"]
    assert "audit_events" in data["tables"]


def test_readiness_with_storage(client):
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database_ready"] is True
    assert data["audit_store_ready"] is True


def test_case_persistence_and_audit_integrity_endpoints(client):
    # Execute a demo case first
    post_res = client.post("/api/v1/demo-cases/DAY10-01-CLEAN-1TO1/run")
    assert post_res.status_code == 200

    # Query persistence status
    persist_res = client.get("/api/v1/cases/DAY10-01-CLEAN-1TO1/persistence")
    assert persist_res.status_code == 200
    p_data = persist_res.json()
    assert p_data["case_id"] == "DAY10-01-CLEAN-1TO1"
    assert p_data["is_persisted"] is True
    assert p_data["audit_event_count"] >= 1

    # Query audit integrity
    audit_res = client.get("/api/v1/cases/DAY10-01-CLEAN-1TO1/audit/integrity")
    assert audit_res.status_code == 200
    a_data = audit_res.json()
    assert a_data["is_valid"] is True
    assert a_data["total_events"] >= 1
    assert a_data["latest_state_hash"] is not None
