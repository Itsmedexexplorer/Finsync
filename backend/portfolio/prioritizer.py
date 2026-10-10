"""VERITY Portfolio Prioritization Engine (Day 15).

Calculates a deterministic PortfolioPriorityScore that combines Controller risk,
deterministic contradiction severity, human review requirements, SLA urgency,
monetary exposure magnitude, and unresolved issue counts.

Strict Invariants:
1. Controller risk remains authoritative.
2. Explanations must be 100% deterministic and grounded in case facts.
"""

from __future__ import annotations

from typing import List, Tuple

from backend.portfolio.models import (
    CasePortfolioItem,
    PortfolioPriority,
    PortfolioPriorityScore,
    SLAStatus,
)


class PortfolioPrioritizer:
    """Deterministic score and priority calculator for portfolio cases."""

    @staticmethod
    def calculate_priority_score(item: CasePortfolioItem) -> PortfolioPriorityScore:
        """Computes a deterministic priority score and rationale."""
        score = 0.0
        reasons: List[str] = []

        # 1. Controller Risk Base
        risk = item.risk_level.upper()
        if risk == "CRITICAL":
            score += 50.0
            reasons.append("CRITICAL risk level assigned by controller policy")
        elif risk == "HIGH":
            score += 30.0
            reasons.append("HIGH risk level assigned by controller policy")
        elif risk == "MEDIUM":
            score += 15.0
            reasons.append("MEDIUM risk level assigned by controller policy")
        else:
            score += 5.0

        # 2. SLA Urgency
        if item.sla_status == SLAStatus.OVERDUE:
            score += 25.0
            reasons.append("Operational SLA deadline is OVERDUE")
        elif item.sla_status == SLAStatus.DUE_SOON:
            score += 10.0
            reasons.append("Operational SLA deadline is DUE SOON (remaining window <= 20%)")

        # 3. Contradictions & Discrepancies
        if item.deterministic_status == "CONTRADICTED":
            score += 15.0
            reasons.append("Case has unresolved deterministic financial contradictions")

        if item.discrepancy_ids:
            disc_count = len(item.discrepancy_ids)
            score += min(15.0, disc_count * 5.0)
            reasons.append(f"{disc_count} active financial discrepancy record(s) flagged")

        # 4. Human Review Requirement
        if item.requires_human_review:
            score += 10.0
            reasons.append("Human controller review is mandatory")

        # 5. Monetary Exposure Weighting
        exp = item.amount_exposure
        if exp >= 100000.0:
            score += 15.0
            reasons.append(f"High monetary exposure of INR {exp:,.2f}")
        elif exp >= 25000.0:
            score += 10.0
            reasons.append(f"Significant monetary exposure of INR {exp:,.2f}")
        elif exp >= 5000.0:
            score += 5.0

        # 6. Unresolved Issues Count
        if item.unresolved_issue_count > 1:
            score += min(10.0, item.unresolved_issue_count * 2.0)
            reasons.append(f"{item.unresolved_issue_count} unresolved case issues identified")

        # 7. Priority Determination
        if score >= 80.0 or risk == "CRITICAL" or item.sla_status == SLAStatus.OVERDUE:
            priority = PortfolioPriority.CRITICAL
        elif score >= 45.0 or risk == "HIGH":
            priority = PortfolioPriority.HIGH
        elif score >= 20.0 or risk == "MEDIUM":
            priority = PortfolioPriority.MEDIUM
        else:
            priority = PortfolioPriority.LOW

        return PortfolioPriorityScore(
            case_id=item.case_id,
            score=round(score, 1),
            priority=priority,
            reasons=reasons,
            supporting_case_id=item.source_case_id,
            discrepancy_ids=list(item.discrepancy_ids),
            transaction_ids=list(item.transaction_ids),
        )
