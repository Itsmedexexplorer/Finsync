"""Rate limiting, fail-closed auth and input length limits."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import rate_limit as rl
from backend.api.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _upload(client):
    csv = Path("data/samples/day2/bank_statement.csv").read_bytes()
    return client.post("/api/v1/cases/files", files=[("files", ("b.csv", csv, "text/csv"))])


def test_uploads_are_rate_limited_per_user(client, monkeypatch):
    monkeypatch.setattr(rl, "UPLOAD_LIMITS", (rl.Limit(2, 60),))
    assert _upload(client).status_code == 200
    assert _upload(client).status_code == 200
    res = _upload(client)
    assert res.status_code == 429
    assert int(res.headers["retry-after"]) > 0
    assert "Too many requests" in res.json()["error"]["message"]


def test_ip_limit_applies_to_all_api_calls(client, monkeypatch):
    monkeypatch.setattr(rl, "IP_LIMIT", rl.Limit(3, 60))
    codes = [client.get("/api/v1/checks").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]


def test_invalid_tokens_are_throttled(client, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    monkeypatch.setattr(rl, "UNAUTHENTICATED_LIMIT", rl.Limit(2, 60))

    async def reject(token):
        return None

    from backend.api import auth
    monkeypatch.setattr(auth, "_verify_token", reject)
    headers = {"Authorization": "Bearer guess"}
    codes = [client.get("/api/v1/checks", headers=headers).status_code for _ in range(3)]
    assert codes == [401, 401, 429]


def test_production_without_supabase_fails_closed(client, monkeypatch):
    monkeypatch.setenv("VERITY_ENV", "production")
    assert client.get("/api/v1/checks").status_code == 503
    assert client.get("/api/v1/config").json()["auth_required"] is True


def test_note_and_question_length_limits(client):
    case_id = _upload(client).json()["case_id"]
    client.get(f"/api/v1/cases/{case_id}/review")
    assert client.post(f"/api/v1/cases/{case_id}/review/note", json={"content": "x" * 2001}).status_code == 400
    assert client.post(f"/api/v1/cases/{case_id}/controller/explain", json={"question": "x" * 501}).status_code == 400
