"""Unit tests for SLA and Case Aging Engine."""

from datetime import datetime, timedelta, timezone
import pytest
from backend.portfolio.models import PortfolioPriority, SLAStatus
from backend.portfolio.sla import SLAPolicy


def test_sla_policy_due_date_calculation() -> None:
    now = datetime(2026, 8, 24, 10, 0, 0, tzinfo=timezone.utc)
    # Critical: 4 hours
    crit_due = SLAPolicy.calculate_due_date(now, PortfolioPriority.CRITICAL)
    assert crit_due == now + timedelta(hours=4)

    # High: 24 hours
    high_due = SLAPolicy.calculate_due_date(now, PortfolioPriority.HIGH)
    assert high_due == now + timedelta(hours=24)


def test_sla_evaluation_statuses() -> None:
    created = datetime(2026, 8, 24, 10, 0, 0, tzinfo=timezone.utc)

    # On Track: 1 hour in on a 24h SLA
    eval_now = created + timedelta(hours=1)
    stat, _, elapsed, rem = SLAPolicy.evaluate_sla(created, PortfolioPriority.HIGH, now=eval_now)
    assert stat == SLAStatus.ON_TRACK
    assert elapsed == 1.0
    assert rem == 23.0

    # Due Soon: 21 hours in on a 24h SLA (remaining 3h <= 20% of 24h = 4.8h)
    eval_now = created + timedelta(hours=21)
    stat, _, _, _ = SLAPolicy.evaluate_sla(created, PortfolioPriority.HIGH, now=eval_now)
    assert stat == SLAStatus.DUE_SOON

    # Overdue: 26 hours in on a 24h SLA
    eval_now = created + timedelta(hours=26)
    stat, _, _, _ = SLAPolicy.evaluate_sla(created, PortfolioPriority.HIGH, now=eval_now)
    assert stat == SLAStatus.OVERDUE

    # Completed: Resolved case
    stat, _, _, _ = SLAPolicy.evaluate_sla(created, PortfolioPriority.HIGH, is_resolved_or_closed=True, now=eval_now)
    assert stat == SLAStatus.COMPLETED
