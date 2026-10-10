"""VERITY SLA & Case Aging Engine (Day 15).

Calculates deterministic SLA deadlines, remaining/elapsed durations,
and SLA operational health statuses (ON_TRACK, DUE_SOON, OVERDUE, PAUSED, COMPLETED).

Strict Invariant:
SLA calculations are purely operational metadata and must NEVER mutate
the underlying deterministic financial truth.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from backend.portfolio.models import PortfolioPriority, SLAStatus

# Default SLA Window Policies
SLA_HOURS_MAP = {
    PortfolioPriority.CRITICAL: 4.0,     # 4 hours
    PortfolioPriority.HIGH: 24.0,        # 24 hours
    PortfolioPriority.MEDIUM: 72.0,      # 72 hours (3 days)
    PortfolioPriority.LOW: 168.0,        # 168 hours (7 days)
}

DUE_SOON_THRESHOLD_RATIO = 0.20  # Remaining <= 20% of SLA window


class SLAPolicy:
    """Deterministic SLA engine for financial case lifecycle management."""

    @staticmethod
    def get_sla_window_hours(priority: PortfolioPriority) -> float:
        """Returns the SLA window duration in hours for a given priority."""
        return SLA_HOURS_MAP.get(priority, 72.0)

    @staticmethod
    def calculate_due_date(created_at: datetime, priority: PortfolioPriority) -> datetime:
        """Computes the target SLA deadline from creation timestamp and priority."""
        hours = SLAPolicy.get_sla_window_hours(priority)
        return created_at + timedelta(hours=hours)

    @staticmethod
    def evaluate_sla(
        created_at: datetime,
        priority: PortfolioPriority,
        is_resolved_or_closed: bool = False,
        is_waiting_for_evidence: bool = False,
        now: Optional[datetime] = None,
    ) -> Tuple[SLAStatus, datetime, float, float]:
        """Evaluates SLA health.

        Returns:
            Tuple of (SLAStatus, due_at, elapsed_hours, remaining_hours)
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # Ensure timezone awareness
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        window_hours = SLAPolicy.get_sla_window_hours(priority)
        due_at = created_at + timedelta(hours=window_hours)

        elapsed_seconds = (now - created_at).total_seconds()
        elapsed_hours = max(0.0, elapsed_seconds / 3600.0)
        remaining_hours = (due_at - now).total_seconds() / 3600.0

        if is_resolved_or_closed:
            return SLAStatus.COMPLETED, due_at, elapsed_hours, max(0.0, remaining_hours)

        if is_waiting_for_evidence:
            return SLAStatus.PAUSED, due_at, elapsed_hours, max(0.0, remaining_hours)

        if now > due_at:
            return SLAStatus.OVERDUE, due_at, elapsed_hours, remaining_hours

        # If remaining duration is <= 20% of the total SLA window
        if remaining_hours <= (window_hours * DUE_SOON_THRESHOLD_RATIO):
            return SLAStatus.DUE_SOON, due_at, elapsed_hours, remaining_hours

        return SLAStatus.ON_TRACK, due_at, elapsed_hours, remaining_hours
