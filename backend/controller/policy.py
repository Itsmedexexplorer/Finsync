"""Deterministic Controller Policy Engine for VERITY.

Enforces deterministic risk classification and action verdicts based strictly on
signals derived from the financial reconciliation pipeline.
"""

from __future__ import annotations

from typing import List, Tuple
from backend.controller.models import (
    ControllerActionType,
    ControllerRiskLevel,
)
from backend.controller.signals import ControllerSignal, ControllerSignalType


class ControllerPolicyEngine:
    """Evaluates extracted controller signals to determine risk level, human review requirements, and primary action."""

    @classmethod
    def evaluate(cls, signals: List[ControllerSignal]) -> Tuple[ControllerRiskLevel, ControllerActionType, bool, List[str]]:
        """Evaluates signals and returns (risk_level, action, requires_human_review, reasons)."""
        reasons: List[str] = []
        if not signals:
            return (
                ControllerRiskLevel.NONE,
                ControllerActionType.NO_ACTION,
                False,
                ["No signals or discrepancies detected; case is fully settled."],
            )

        has_critical = False
        has_high = False
        has_medium = False
        has_partial = False
        has_unmatched = False
        has_unverifiable = False
        has_ambiguity = False
        has_entity_issue = False
        has_amount_issue = False
        has_ref_issue = False
        has_confirmed = False

        for s in signals:
            reasons.append(s.message)
            if s.severity == ControllerRiskLevel.CRITICAL:
                has_critical = True
            elif s.severity == ControllerRiskLevel.HIGH:
                has_high = True
            elif s.severity == ControllerRiskLevel.MEDIUM:
                has_medium = True

            if s.signal_type in (ControllerSignalType.ENTITY_MISMATCH, ControllerSignalType.AMBIGUOUS_ENTITY):
                has_entity_issue = True
            elif s.signal_type == ControllerSignalType.AMOUNT_MISMATCH:
                has_amount_issue = True
            elif s.signal_type in (ControllerSignalType.REFERENCE_MISMATCH, ControllerSignalType.CONFLICTING_CLAIMS, ControllerSignalType.CRITICAL_CONTRADICTION):
                has_ref_issue = True
            elif s.signal_type == ControllerSignalType.AMBIGUOUS_TRANSACTION:
                has_ambiguity = True
            elif s.signal_type == ControllerSignalType.PARTIAL_SETTLEMENT:
                has_partial = True
            elif s.signal_type == ControllerSignalType.UNMATCHED_TRANSACTION:
                has_unmatched = True
            elif s.signal_type in (ControllerSignalType.UNVERIFIABLE_CLAIM, ControllerSignalType.MISSING_EVIDENCE):
                has_unverifiable = True
            elif s.signal_type == ControllerSignalType.CONFIRMED_RECONCILIATION:
                has_confirmed = True

        # Policy Rule 1: Critical Contradictions & Misroutes
        if has_critical:
            action = ControllerActionType.INVESTIGATE_CONTRADICTION
            if has_entity_issue:
                action = ControllerActionType.VERIFY_ENTITY
            return (ControllerRiskLevel.CRITICAL, action, True, reasons)

        # Policy Rule 2: High Severity Issues (Amount/Ref Mismatch, Ambiguities)
        if has_high:
            if has_amount_issue or has_ref_issue:
                action = ControllerActionType.INVESTIGATE_CONTRADICTION
            elif has_entity_issue:
                action = ControllerActionType.VERIFY_ENTITY
            elif has_ambiguity:
                action = ControllerActionType.REVIEW_CASE
            else:
                action = ControllerActionType.REVIEW_CASE
            return (ControllerRiskLevel.HIGH, action, True, reasons)

        # Policy Rule 3: Partial Settlement & Outstanding Balances
        if has_partial:
            return (
                ControllerRiskLevel.MEDIUM,
                ControllerActionType.VERIFY_TRANSACTION,
                True,
                reasons,
            )

        # Policy Rule 4: Unmatched Bank Transactions
        if has_unmatched:
            return (
                ControllerRiskLevel.MEDIUM,
                ControllerActionType.VERIFY_TRANSACTION,
                True,
                reasons,
            )

        # Policy Rule 5: Unverifiable Claims / Missing Evidence
        if has_unverifiable:
            return (
                ControllerRiskLevel.MEDIUM,
                ControllerActionType.REQUEST_MISSING_EVIDENCE,
                True,
                reasons,
            )

        # Policy Rule 6: Confirmed Clean Cases
        if has_confirmed or (not has_medium and not has_high and not has_critical):
            return (
                ControllerRiskLevel.NONE,
                ControllerActionType.CONFIRM_RECONCILIATION,
                False,
                reasons,
            )

        # Fallback for minor medium signals
        return (
            ControllerRiskLevel.MEDIUM,
            ControllerActionType.REVIEW_CASE,
            True,
            reasons,
        )
