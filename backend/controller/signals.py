"""Deterministic signal extraction for the VERITY AI Finance Controller."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.case_processing.result import CaseProcessingResult
from backend.controller.models import ControllerRiskLevel


class ControllerSignalType(str, Enum):
    """Categorized signals extracted deterministically from case processing results."""
    # Critical Discrepancy Signals
    ENTITY_MISMATCH = "ENTITY_MISMATCH"
    DIRECTION_MISMATCH = "DIRECTION_MISMATCH"
    CRITICAL_CONTRADICTION = "CRITICAL_CONTRADICTION"

    # High Severity Signals
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    REFERENCE_MISMATCH = "REFERENCE_MISMATCH"
    CONFLICTING_CLAIMS = "CONFLICTING_CLAIMS"
    DATE_MISMATCH = "DATE_MISMATCH"

    # Ambiguity & Settlement Signals
    AMBIGUOUS_ENTITY = "AMBIGUOUS_ENTITY"
    AMBIGUOUS_TRANSACTION = "AMBIGUOUS_TRANSACTION"
    PARTIAL_SETTLEMENT = "PARTIAL_SETTLEMENT"
    UNMATCHED_TRANSACTION = "UNMATCHED_TRANSACTION"
    UNVERIFIABLE_CLAIM = "UNVERIFIABLE_CLAIM"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"

    # Positive & Informational Signals
    CONFIRMED_RECONCILIATION = "CONFIRMED_RECONCILIATION"
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


class ControllerSignal(BaseModel):
    """An individual verifiable signal extracted from deterministic pipeline results."""
    signal_type: ControllerSignalType = Field(..., description="Classification of the signal")
    severity: ControllerRiskLevel = Field(..., description="Risk severity associated with this signal")
    weight: float = Field(default=1.0, description="Relative significance score")
    message: str = Field(..., description="Clear explanation of the signal")
    affected_ids: List[str] = Field(default_factory=list, description="IDs of involved objects")
    amount: Optional[float] = Field(default=None, description="Relevant monetary amount if applicable")
    source_stage: str = Field(default="RECONCILIATION", description="Pipeline stage that produced the signal")


class SignalExtractor:
    """Extracts transparent controller signals solely from deterministic CaseProcessingResult data."""

    @classmethod
    def extract_signals(cls, result: CaseProcessingResult) -> List[ControllerSignal]:
        """Inspects result, report, reconciliation, and matching data to derive signals."""
        signals: List[ControllerSignal] = []

        # 1. Inspect Discrepancies from Report
        discs = []
        if result.report and result.report.contradiction_summary:
            discs = result.report.contradiction_summary

        for disc in discs:
            disc_type = disc.discrepancy_type.upper()
            disc_sev = disc.severity.upper()
            involved = list(disc.involved_evidence_ids) + [disc.discrepancy_id]

            if disc_type == "ENTITY_MISMATCH":
                sev = ControllerRiskLevel.CRITICAL if disc_sev == "CRITICAL" else ControllerRiskLevel.HIGH
                signals.append(ControllerSignal(
                    signal_type=ControllerSignalType.ENTITY_MISMATCH,
                    severity=sev,
                    weight=3.0 if sev == ControllerRiskLevel.CRITICAL else 2.5,
                    message=f"Entity mismatch detected: {disc.message}",
                    affected_ids=involved,
                    source_stage="CONTRADICTION_DETECTION",
                ))
            elif disc_type == "DIRECTION_MISMATCH":
                signals.append(ControllerSignal(
                    signal_type=ControllerSignalType.DIRECTION_MISMATCH,
                    severity=ControllerRiskLevel.CRITICAL,
                    weight=3.0,
                    message=f"Payment flow direction conflict: {disc.message}",
                    affected_ids=involved,
                    source_stage="CONTRADICTION_DETECTION",
                ))
            elif disc_type == "AMOUNT_MISMATCH":
                sev = ControllerRiskLevel.CRITICAL if disc_sev == "CRITICAL" else ControllerRiskLevel.HIGH
                signals.append(ControllerSignal(
                    signal_type=ControllerSignalType.AMOUNT_MISMATCH,
                    severity=sev,
                    weight=2.5,
                    message=f"Monetary amount contradiction: {disc.message}",
                    affected_ids=involved,
                    source_stage="CONTRADICTION_DETECTION",
                ))
            elif disc_type == "REFERENCE_MISMATCH":
                sev = ControllerRiskLevel.CRITICAL if disc_sev == "CRITICAL" else ControllerRiskLevel.HIGH
                signals.append(ControllerSignal(
                    signal_type=ControllerSignalType.REFERENCE_MISMATCH,
                    severity=sev,
                    weight=2.0,
                    message=f"Bank reference contradiction: {disc.message}",
                    affected_ids=involved,
                    source_stage="CONTRADICTION_DETECTION",
                ))
            elif disc_type == "CONFLICTING_CLAIMS":
                signals.append(ControllerSignal(
                    signal_type=ControllerSignalType.CONFLICTING_CLAIMS,
                    severity=ControllerRiskLevel.HIGH,
                    weight=2.0,
                    message=f"Conflicting claims across evidence sources: {disc.message}",
                    affected_ids=involved,
                    source_stage="CONTRADICTION_DETECTION",
                ))
            elif disc_type == "DATE_MISMATCH":
                signals.append(ControllerSignal(
                    signal_type=ControllerSignalType.DATE_MISMATCH,
                    severity=ControllerRiskLevel.MEDIUM,
                    weight=1.5,
                    message=f"Date mismatch: {disc.message}",
                    affected_ids=involved,
                    source_stage="CONTRADICTION_DETECTION",
                ))
            else:
                sev = ControllerRiskLevel.CRITICAL if disc_sev == "CRITICAL" else ControllerRiskLevel.HIGH
                signals.append(ControllerSignal(
                    signal_type=ControllerSignalType.CRITICAL_CONTRADICTION,
                    severity=sev,
                    weight=2.0,
                    message=disc.message,
                    affected_ids=involved,
                    source_stage="CONTRADICTION_DETECTION",
                ))

        # 2. Inspect Matching Summary from Report
        if result.report and result.report.matching_summary:
            ms = result.report.matching_summary
            if ms.status.upper() == "AMBIGUOUS":
                signals.append(ControllerSignal(
                    signal_type=ControllerSignalType.AMBIGUOUS_TRANSACTION,
                    severity=ControllerRiskLevel.HIGH,
                    weight=2.5,
                    message=f"Ambiguous transaction matching ({ms.explanation})",
                    affected_ids=[ms.match_relationship_id] if ms.match_relationship_id else [],
                    source_stage="TRANSACTION_MATCHING",
                ))
            elif ms.topology.upper() == "PARTIAL":
                fin_sum = result.financial_summary or {}
                out_amt = fin_sum.get("outstanding_amount", 0.0)
                matched_amt = fin_sum.get("matched_amount", 0.0)
                signals.append(ControllerSignal(
                    signal_type=ControllerSignalType.PARTIAL_SETTLEMENT,
                    severity=ControllerRiskLevel.MEDIUM,
                    weight=1.8,
                    message=f"Partial settlement: INR {matched_amt:,.2f} matched (Outstanding: INR {out_amt:,.2f})",
                    affected_ids=[ms.match_relationship_id] if ms.match_relationship_id else [],
                    amount=out_amt,
                    source_stage="TRANSACTION_MATCHING",
                ))

        # 3. Inspect Reconciliation Status & Outstanding Amounts
        status_val = result.status.upper()
        fin_sum = result.financial_summary or {}
        out_bal = fin_sum.get("outstanding_amount", 0.0)
        confidence = getattr(result, "confidence_score", getattr(result, "confidence", 1.0))

        if status_val == "CONTRADICTED":
            if not signals:
                signals.append(ControllerSignal(
                    signal_type=ControllerSignalType.CRITICAL_CONTRADICTION,
                    severity=ControllerRiskLevel.CRITICAL,
                    weight=3.0,
                    message="Case reconciliation terminated with CONTRADICTED status",
                    affected_ids=[result.case_id],
                    source_stage="RECONCILIATION",
                ))
        elif status_val == "AMBIGUOUS":
            if not any(s.signal_type == ControllerSignalType.AMBIGUOUS_TRANSACTION for s in signals):
                signals.append(ControllerSignal(
                    signal_type=ControllerSignalType.AMBIGUOUS_TRANSACTION,
                    severity=ControllerRiskLevel.HIGH,
                    weight=2.5,
                    message="Case reconciliation is AMBIGUOUS due to multiple candidate matches",
                    affected_ids=[result.case_id],
                    source_stage="RECONCILIATION",
                ))
        elif status_val in ("PARTIAL", "PARTIALLY_SETTLED"):
            if not any(s.signal_type == ControllerSignalType.PARTIAL_SETTLEMENT for s in signals):
                signals.append(ControllerSignal(
                    signal_type=ControllerSignalType.PARTIAL_SETTLEMENT,
                    severity=ControllerRiskLevel.MEDIUM,
                    weight=1.8,
                    message=f"Case partially settled with outstanding balance of INR {out_bal:,.2f}",
                    affected_ids=[result.case_id],
                    amount=out_bal,
                    source_stage="RECONCILIATION",
                ))
        elif status_val == "UNMATCHED":
            signals.append(ControllerSignal(
                signal_type=ControllerSignalType.UNMATCHED_TRANSACTION,
                severity=ControllerRiskLevel.MEDIUM,
                weight=1.5,
                message="Unmatched transaction without supporting invoice or claim",
                affected_ids=[result.case_id],
                amount=fin_sum.get("matched_amount", 0.0),
                source_stage="RECONCILIATION",
            ))
        elif status_val == "UNVERIFIABLE":
            signals.append(ControllerSignal(
                signal_type=ControllerSignalType.UNVERIFIABLE_CLAIM,
                severity=ControllerRiskLevel.MEDIUM,
                weight=1.5,
                message="Claim cannot be verified due to missing transaction records or unquantified evidence",
                affected_ids=[result.case_id],
                source_stage="RECONCILIATION",
            ))
        elif status_val == "CONFIRMED":
            if len(signals) == 0:
                signals.append(ControllerSignal(
                    signal_type=ControllerSignalType.CONFIRMED_RECONCILIATION,
                    severity=ControllerRiskLevel.NONE,
                    weight=0.0,
                    message="Reconciliation fully confirmed with 100% mathematical certainty",
                    affected_ids=[result.case_id],
                    amount=fin_sum.get("matched_amount", 0.0),
                    source_stage="RECONCILIATION",
                ))

        # 4. Inspect Confidence
        if confidence < 0.70 and status_val != "CONFIRMED":
            signals.append(ControllerSignal(
                signal_type=ControllerSignalType.LOW_CONFIDENCE,
                severity=ControllerRiskLevel.MEDIUM,
                weight=1.0,
                message=f"Low reconciliation confidence ({confidence * 100:.0f}%)",
                affected_ids=[result.case_id],
                source_stage="RECONCILIATION",
            ))

        return signals
