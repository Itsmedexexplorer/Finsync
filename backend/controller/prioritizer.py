"""Action Prioritization for the VERITY AI Finance Controller."""

from __future__ import annotations

from typing import List
from backend.controller.models import (
    ControllerActionType,
    ControllerRecommendation,
    ControllerRiskLevel,
)
from backend.controller.signals import ControllerSignal, ControllerSignalType


class ActionPrioritizer:
    """Prioritizes and constructs deterministic ControllerRecommendations from extracted signals."""

    @classmethod
    def prioritize(cls, signals: List[ControllerSignal]) -> List[ControllerRecommendation]:
        """Maps signals to ranked, actionable recommendations."""
        recommendations: List[ControllerRecommendation] = []
        if not signals:
            return [
                ControllerRecommendation(
                    action_type=ControllerActionType.CONFIRM_RECONCILIATION,
                    priority=10,
                    title="Authorize Automated Ledger Posting",
                    explanation="All claims and transactions match with 100% mathematical certainty.",
                    rationale="No discrepancies or unverified records detected.",
                    supporting_ids=[],
                    blocking_issue=False,
                    requires_human_action=False,
                )
            ]

        for s in signals:
            if s.signal_type == ControllerSignalType.ENTITY_MISMATCH:
                recommendations.append(ControllerRecommendation(
                    action_type=ControllerActionType.VERIFY_ENTITY,
                    priority=1,
                    title="Resolve Counterparty Identity Mismatch",
                    explanation="Claimed counterparty differs from verified banking identity.",
                    rationale=s.message,
                    supporting_ids=s.affected_ids,
                    blocking_issue=True,
                    requires_human_action=True,
                ))
            elif s.signal_type == ControllerSignalType.DIRECTION_MISMATCH:
                recommendations.append(ControllerRecommendation(
                    action_type=ControllerActionType.INVESTIGATE_CONTRADICTION,
                    priority=1,
                    title="Investigate Payment Flow Direction Conflict",
                    explanation="Claim indicates outgoing payment while bank record shows credit, or vice versa.",
                    rationale=s.message,
                    supporting_ids=s.affected_ids,
                    blocking_issue=True,
                    requires_human_action=True,
                ))
            elif s.signal_type == ControllerSignalType.AMOUNT_MISMATCH:
                recommendations.append(ControllerRecommendation(
                    action_type=ControllerActionType.INVESTIGATE_CONTRADICTION,
                    priority=2,
                    title="Audit Monetary Amount Discrepancy",
                    explanation="Invoiced amount does not equal settled banking transaction value.",
                    rationale=s.message,
                    supporting_ids=s.affected_ids,
                    blocking_issue=True,
                    requires_human_action=True,
                ))
            elif s.signal_type == ControllerSignalType.REFERENCE_MISMATCH:
                recommendations.append(ControllerRecommendation(
                    action_type=ControllerActionType.INVESTIGATE_CONTRADICTION,
                    priority=2,
                    title="Verify Bank Reference / UTR Number",
                    explanation="Referenced transaction identifier does not match verified bank records.",
                    rationale=s.message,
                    supporting_ids=s.affected_ids,
                    blocking_issue=True,
                    requires_human_action=True,
                ))
            elif s.signal_type == ControllerSignalType.AMBIGUOUS_TRANSACTION:
                recommendations.append(ControllerRecommendation(
                    action_type=ControllerActionType.REVIEW_CASE,
                    priority=3,
                    title="Disambiguate Multiple Transaction Candidates",
                    explanation="Multiple candidate transactions match the same financial claim.",
                    rationale=s.message,
                    supporting_ids=s.affected_ids,
                    blocking_issue=True,
                    requires_human_action=True,
                ))
            elif s.signal_type == ControllerSignalType.PARTIAL_SETTLEMENT:
                recommendations.append(ControllerRecommendation(
                    action_type=ControllerActionType.VERIFY_TRANSACTION,
                    priority=4,
                    title="Track Remaining Outstanding Balance",
                    explanation="Payment partially covers invoice total. Follow up for remaining balance.",
                    rationale=s.message,
                    supporting_ids=s.affected_ids,
                    blocking_issue=False,
                    requires_human_action=True,
                ))
            elif s.signal_type == ControllerSignalType.UNMATCHED_TRANSACTION:
                recommendations.append(ControllerRecommendation(
                    action_type=ControllerActionType.VERIFY_TRANSACTION,
                    priority=5,
                    title="Identify Source for Unmatched Bank Transaction",
                    explanation="Bank statement contains credit without associated claim or invoice.",
                    rationale=s.message,
                    supporting_ids=s.affected_ids,
                    blocking_issue=False,
                    requires_human_action=True,
                ))
            elif s.signal_type in (ControllerSignalType.UNVERIFIABLE_CLAIM, ControllerSignalType.MISSING_EVIDENCE):
                recommendations.append(ControllerRecommendation(
                    action_type=ControllerActionType.REQUEST_MISSING_EVIDENCE,
                    priority=6,
                    title="Request Supporting Payment Proof / Bank Statement",
                    explanation="Informal payment claim cannot be validated against bank records.",
                    rationale=s.message,
                    supporting_ids=s.affected_ids,
                    blocking_issue=True,
                    requires_human_action=True,
                ))
            elif s.signal_type == ControllerSignalType.CONFIRMED_RECONCILIATION:
                recommendations.append(ControllerRecommendation(
                    action_type=ControllerActionType.CONFIRM_RECONCILIATION,
                    priority=10,
                    title="Authorize Automated Settlement",
                    explanation="Reconciliation confirmed with zero discrepancies.",
                    rationale=s.message,
                    supporting_ids=s.affected_ids,
                    blocking_issue=False,
                    requires_human_action=False,
                ))

        # Sort recommendations by priority ascending (1 = highest urgency)
        recommendations.sort(key=lambda r: r.priority)
        return recommendations
