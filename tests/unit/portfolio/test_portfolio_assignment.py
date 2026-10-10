"""Unit tests for Case Assignment and Workload tracking."""

import pytest
from backend.portfolio.assignment import PortfolioAssignmentService
from backend.portfolio.models import CasePortfolioItem, PortfolioCaseStatus, PortfolioPriority, SLAStatus


def test_assignment_lifecycle() -> None:
    svc = PortfolioAssignmentService()

    # Assign
    asg = svc.assign_case("CASE-100", "ctrl_alice", "Alice Senior Controller")
    assert asg.case_id == "CASE-100"
    assert asg.reviewer_id == "ctrl_alice"
    assert asg.active is True

    # Reassign
    re_asg = svc.reassign_case("CASE-100", "ctrl_bob", "Bob Lead Controller")
    assert re_asg.reviewer_id == "ctrl_bob"
    assert re_asg.active is True

    # Unassign
    un_asg = svc.unassign_case("CASE-100")
    assert un_asg is not None
    assert un_asg.active is False
    assert svc.get_assignment("CASE-100") is None


def test_reviewer_workload_and_overload() -> None:
    svc = PortfolioAssignmentService()
    cases = []

    # Create 7 critical open cases assigned to Alice (>5 triggers overload)
    for i in range(7):
        cases.append(
            CasePortfolioItem(
                case_id=f"CASE-CRIT-{i}",
                source_case_id=f"CASE-CRIT-{i}",
                deterministic_status="CONTRADICTED",
                portfolio_status=PortfolioCaseStatus.IN_REVIEW,
                priority=PortfolioPriority.CRITICAL,
                risk_level="CRITICAL",
                assigned_reviewer_id="ctrl_alice",
                assigned_reviewer_name="Alice",
                amount_exposure=10000.0,
            )
        )

    workloads = svc.list_workloads(cases)
    assert len(workloads) == 1
    w = workloads[0]
    assert w.reviewer_id == "ctrl_alice"
    assert w.assigned_cases == 7
    assert w.critical_cases == 7
    assert w.is_overloaded is True
    assert any("critical" in r.lower() for r in w.overload_reasons)
