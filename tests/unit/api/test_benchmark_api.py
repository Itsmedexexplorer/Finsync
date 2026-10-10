"""Tests for the Track 04 Benchmark Batch Reconciliation API endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_benchmark_endpoint_returns_at_least_50_cases(client: TestClient) -> None:
    """Test requirement 1: Endpoint returns >= 50 cases (Track 04 requirement)."""
    response = client.post("/api/v1/benchmark/run")
    assert response.status_code == 200
    data = response.json()
    assert data["total_cases"] >= 50
    assert data["total_cases"] == 96
    assert len(data["cases"]) == data["total_cases"]


def test_benchmark_total_cases_matches_actual_result_count(client: TestClient) -> None:
    """Test requirement 2: total_cases matches actual processed result count."""
    response = client.post("/api/v1/benchmark/run")
    assert response.status_code == 200
    data = response.json()
    assert data["total_cases"] == len(data["cases"])
    assert data["total_evidence_items"] > 0
    assert data["total_claims"] > 0
    assert data["total_transactions"] > 0


def test_benchmark_monetary_match_rate_calculated_accurately(client: TestClient) -> None:
    """Test requirement 3: monetary_match_rate is mathematically calculated from returned values."""
    response = client.post("/api/v1/benchmark/run")
    assert response.status_code == 200
    data = response.json()
    claimed = data["total_claimed_value"]
    reconciled = data["total_reconciled_value"]
    assert claimed > 0.0
    expected_rate = round((reconciled / claimed) * 100.0, 2)
    assert abs(data["monetary_match_rate"] - expected_rate) < 0.05


def test_benchmark_status_distribution_sums_to_total_cases(client: TestClient) -> None:
    """Test requirement 4: status_distribution counts sum exactly to total_cases."""
    response = client.post("/api/v1/benchmark/run")
    assert response.status_code == 200
    data = response.json()
    dist = data["status_distribution"]
    sum_dist = sum(dist.values())
    assert sum_dist == data["total_cases"]
    assert "CONFIRMED" in dist
    assert "CONTRADICTED" in dist
    assert "UNVERIFIABLE" in dist


def test_benchmark_exception_counts_from_actual_pipeline_results(client: TestClient) -> None:
    """Test requirement 5: exception counts come from actual pipeline discrepancy outputs."""
    response = client.post("/api/v1/benchmark/run")
    assert response.status_code == 200
    data = response.json()
    exceptions = data["exception_breakdown"]
    assert len(exceptions) > 0
    assert "REFERENCE_MISMATCH" in exceptions
    assert exceptions["REFERENCE_MISMATCH"] > 0


def test_benchmark_execution_is_deterministic_and_repeatable(client: TestClient) -> None:
    """Test requirement 6: Repeated benchmark executions produce identical metrics."""
    res1 = client.post("/api/v1/benchmark/run").json()
    res2 = client.post("/api/v1/benchmark/run").json()
    assert res1["total_cases"] == res2["total_cases"]
    assert res1["total_claimed_value"] == res2["total_claimed_value"]
    assert res1["total_reconciled_value"] == res2["total_reconciled_value"]
    assert res1["monetary_match_rate"] == res2["monetary_match_rate"]
    assert res1["status_distribution"] == res2["status_distribution"]
    assert res1["exception_breakdown"] == res2["exception_breakdown"]


def test_benchmark_does_not_pollute_portfolio_or_database(client: TestClient) -> None:
    """Test requirement 7: Benchmark execution does not create normal portfolio/database records."""
    before_portfolio = client.get("/api/v1/portfolio").json()
    client.post("/api/v1/benchmark/run")
    after_portfolio = client.get("/api/v1/portfolio").json()
    assert before_portfolio["total"] == after_portfolio["total"]



def test_existing_demo_cases_remain_intact(client: TestClient) -> None:
    """Test requirement 8: Existing 10 demo cases remain unchanged."""
    demo_res = client.get("/api/v1/demo-cases")
    assert demo_res.status_code == 200
    demo_cases = demo_res.json()
    assert len(demo_cases) == 10
    day10_ids = [c["case_id"] for c in demo_cases]
    assert "DAY10-01-CLEAN-1TO1" in day10_ids
    assert "DAY10-10-ONE-TO-MANY-BULK" in day10_ids
