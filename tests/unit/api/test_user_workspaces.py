"""Tests for per-user workspaces, Supabase auth gating, and bank statement uploads."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import auth
from backend.api.app import app
from backend.config import get_settings

SAMPLES = Path("data/samples/day2")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def two_users(monkeypatch, tmp_path):
    """Enables auth with two fake Supabase users, each with an isolated workspace dir."""
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("VERITY_WORKSPACE_DIR", str(tmp_path))

    users = {"token-a": {"id": "user-a"}, "token-b": {"id": "user-b"}}

    async def fake_verify(token):
        return users.get(token)

    monkeypatch.setattr(auth, "_verify_token", fake_verify)

    from backend import workspace

    for uid in ("user-a", "user-b"):
        workspace._workspaces.pop(uid, None)
    yield {"a": {"Authorization": "Bearer token-a"}, "b": {"Authorization": "Bearer token-b"}}
    for uid in ("user-a", "user-b"):
        workspace._workspaces.pop(uid, None)


def _upload(client, headers=None):
    files = [
        ("files", ("bank_statement.csv", (SAMPLES / "bank_statement.csv").read_bytes(), "text/csv")),
        ("files", ("whatsapp_messages.txt", (SAMPLES / "whatsapp_messages.txt").read_bytes(), "text/plain")),
    ]
    return client.post("/api/v1/cases/files", files=files, headers=headers or {})


def test_bank_statement_rows_become_ledger_transactions(client: TestClient) -> None:
    res = _upload(client)
    assert res.status_code == 200
    summary = res.json()["financial_summary"]
    assert summary["transactions_count"] == 5
    assert summary["matched_amount"] > 0


def test_api_requires_sign_in_when_supabase_configured(client: TestClient, two_users) -> None:
    assert client.get("/api/v1/portfolio").status_code == 401
    assert client.get("/api/v1/portfolio", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/api/v1/config").status_code == 200


def test_new_user_starts_empty_and_users_are_isolated(client: TestClient, two_users) -> None:
    a, b = two_users["a"], two_users["b"]
    assert client.get("/api/v1/portfolio/summary", headers=a).json()["total_cases"] == 0

    case_id = _upload(client, a).json()["case_id"]

    assert client.get("/api/v1/portfolio/summary", headers=a).json()["total_cases"] == 1
    assert client.get("/api/v1/portfolio/summary", headers=b).json()["total_cases"] == 0
    assert client.get(f"/api/v1/cases/{case_id}", headers=b).status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}", headers=a).status_code == 200


def test_review_state_survives_workspace_reload(client: TestClient, two_users) -> None:
    from backend import workspace

    a = two_users["a"]
    case_id = _upload(client, a).json()["case_id"]
    client.get(f"/api/v1/cases/{case_id}/review", headers=a)
    client.post(f"/api/v1/cases/{case_id}/review/note", json={"content": "Called the client"}, headers=a)

    workspace._workspaces.pop("user-a")  # simulate a restart

    review = client.get(f"/api/v1/cases/{case_id}/review", headers=a).json()
    assert [n["content"] for n in review["notes"]] == ["Called the client"]


def test_demo_endpoints_hidden_when_disabled(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "enable_demo", False)
    assert client.get("/api/v1/demo-cases").status_code == 404
    assert client.post("/api/v1/benchmark/run").status_code == 404


def test_checks_people_and_delete(client: TestClient, two_users) -> None:
    a = two_users["a"]
    assert client.get("/api/v1/checks", headers=a).json() == []
    case_id = _upload(client, a).json()["case_id"]

    checks = client.get("/api/v1/checks", headers=a).json()
    assert [c["case_id"] for c in checks] == [case_id]
    assert checks[0]["matched_amount"] > 0
    people = client.get("/api/v1/counterparties", headers=a).json()
    assert people and people[0]["case_ids"] == [case_id]

    assert client.delete(f"/api/v1/checks/{case_id}", headers=a).status_code == 200
    assert client.get("/api/v1/checks", headers=a).json() == []
    assert client.get(f"/api/v1/cases/{case_id}", headers=a).status_code == 404
