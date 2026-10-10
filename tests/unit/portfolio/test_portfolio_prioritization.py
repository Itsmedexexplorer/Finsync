"""Unit tests for Portfolio Prioritization Engine."""

import pytest
from backend.portfolio.models import CasePortfolioItem, PortfolioPriority, SLAStatus
from backend.portfolio.prioritizer import PortfolioPrioritizer


def test_prioritization_critical_case() -> None:
    item = CasePortfolioItem(
        case_id="CASE-PRIO-01",
        source_case_id="CASE-PRIO-01",
        deterministic_status="CONTRADICTED",
        risk_level="CRITICAL",
        amount_exposure=50000.0,
        discrepancy_ids=["DISC-1"],
        sla_status=SLAStatus.OVERDUE,
        requires_human_review=True,
    )
    score = PortfolioPrioritizer.calculate_priority_score(item)
    assert score.priority == PortfolioPriority.CRITICAL
    assert score.score >= 80.0
    assert any("CRITICAL risk" in r for r in score.reasons)
    assert any("OVERDUE" in r for r in score.reasons)


def test_prioritization_clean_case() -> None:
    item = CasePortfolioItem(
        case_id="CASE-PRIO-02",
        source_case_id="CASE-PRIO-02",
        deterministic_status="CONFIRMED",
        risk_level="NONE",
        amount_exposure=1000.0,
        requires_human_review=False,
    )
    score = PortfolioPrioritizer.calculate_priority_score(item)
    assert score.priority == PortfolioPriority.LOW
    assert score.score < 20.0
