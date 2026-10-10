"""Unit tests for Portfolio Workload calculations."""

import pytest
from backend.portfolio.assignment import PortfolioAssignmentService
from backend.portfolio.models import CasePortfolioItem, PortfolioCaseStatus, PortfolioPriority


def test_workload_multiple_reviewers() -> None:
    svc = PortfolioAssignmentService()
    cases = [
        CasePortfolioItem(
            case_id="C1",
            source_case_id="C1",
            deterministic_status="CONTRADICTED",
            portfolio_status=PortfolioCaseStatus.IN_REVIEW,
            priority=PortfolioPriority.HIGH,
            risk_level="HIGH",
            assigned_reviewer_id="ctrl_alice",
            assigned_reviewer_name="Alice",
            amount_exposure=15000.0,
        ),
        CasePortfolioItem(
            case_id="C2",
            source_case_id="C2",
            deterministic_status="CONFIRMED",
            portfolio_status=PortfolioCaseStatus.RESOLVED,
            priority=PortfolioPriority.LOW,
            risk_level="LOW",
            assigned_reviewer_id="ctrl_bob",
            assigned_reviewer_name="Bob",
            amount_exposure=25000.0,
        ),
    ]

    workloads = svc.list_workloads(cases)
    assert len(workloads) == 2
    alice_wl = next(w for w in workloads if w.reviewer_id == "ctrl_alice")
    bob_wl = next(w for w in workloads if w.reviewer_id == "ctrl_bob")

    assert alice_wl.assigned_cases == 1
    assert alice_wl.open_cases == 1
    assert alice_wl.total_exposure == 15000.0

    assert bob_wl.assigned_cases == 1
    assert bob_wl.open_cases == 0  # Resolved case
    assert bob_wl.total_exposure == 25000.0
