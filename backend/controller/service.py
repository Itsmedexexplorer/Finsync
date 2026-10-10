"""Unified AI Finance Controller Service for VERITY."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from backend.case_processing.result import CaseProcessingResult
from backend.controller.ai_explainer import AIExplainer
from backend.controller.context import build_controller_ai_context
from backend.controller.explainability import ControllerExplainabilityEngine
from backend.controller.models import (
    ControllerActionType,
    ControllerBrief,
    ControllerDecision,
    ControllerExplainResponse,
    ControllerRecommendation,
    ControllerRiskLevel,
)
from backend.controller.policy import ControllerPolicyEngine
from backend.controller.prioritizer import ActionPrioritizer
from backend.controller.signals import SignalExtractor


class ControllerService:
    """High-level decision intelligence orchestrator providing risk evaluation, policy verdicts, and explainability."""

    def analyze_case(self, result: CaseProcessingResult) -> ControllerDecision:
        """Evaluates a completed CaseProcessingResult to generate a ControllerDecision."""
        # 1. Deterministic Signal Extraction
        signals = SignalExtractor.extract_signals(result)

        # 2. Deterministic Policy Evaluation
        risk_level, action, requires_review, reasons = ControllerPolicyEngine.evaluate(signals)

        # 3. Action Prioritization
        recommendations = ActionPrioritizer.prioritize(signals)

        # 4. Extract Supporting Provenance IDs
        ev_ids: List[str] = []
        clm_ids: List[str] = []
        txn_ids: List[str] = []
        disc_ids: List[str] = []

        if result.report:
            if result.report.provenance:
                ev_ids = list(result.report.provenance.evidence_ids)
                clm_ids = list(result.report.provenance.claim_ids)
                txn_ids = list(result.report.provenance.transaction_ids)
                disc_ids = list(result.report.provenance.discrepancy_ids)
            elif result.report.contradiction_summary:
                disc_ids = [d.discrepancy_id for d in result.report.contradiction_summary]

        if result.reconciliation:
            if not ev_ids:
                ev_ids = list(result.reconciliation.evidence_ids)
            if not clm_ids:
                clm_ids = list(result.reconciliation.claim_ids)
            if not txn_ids:
                txn_ids = list(result.reconciliation.transaction_ids)
            if not disc_ids:
                disc_ids = list(result.reconciliation.discrepancy_ids)

        confidence = getattr(result, "confidence_score", getattr(result, "confidence", 1.0))
        uncertainty_reasons: List[str] = []
        if confidence < 1.0:
            if result.status == "AMBIGUOUS":
                uncertainty_reasons.append("Multiple candidate transactions with equal matching weight.")
            elif result.status == "UNVERIFIABLE":
                uncertainty_reasons.append("Missing banking statement or unquantified evidence.")
            elif result.status in ("PARTIAL", "PARTIALLY_SETTLED"):
                uncertainty_reasons.append("Unsettled balance remaining on invoice total.")
            elif result.status == "CONTRADICTED":
                uncertainty_reasons.append("Deterministic conflict between claimed and observed records.")

        return ControllerDecision(
            case_id=result.case_id,
            risk_level=risk_level,
            decision=action,
            requires_human_review=requires_review,
            confidence=confidence,
            reasons=reasons,
            supporting_evidence_ids=ev_ids,
            supporting_claim_ids=clm_ids,
            supporting_transaction_ids=txn_ids,
            supporting_discrepancy_ids=disc_ids,
            recommended_actions=recommendations,
            uncertainty_reasons=uncertainty_reasons,
            deterministic_basis={
                "status": result.status,
                "confidence": confidence,
                "signals_count": len(signals),
                "financial_summary": result.financial_summary,
            },
            metadata={"signals_evaluated": len(signals)},
        )

    def build_brief(self, result: CaseProcessingResult) -> ControllerBrief:
        """Constructs an executive controller brief synthesizing case state, financial accounting, and recommendations."""
        decision = self.analyze_case(result)
        context = build_controller_ai_context(result, decision)

        # Generate Grounded Executive Summary
        exec_summary, _ = AIExplainer.generate_brief_summary(context)

        # Unresolved Items
        unresolved: List[str] = []
        if result.report and result.report.contradiction_summary:
            for disc in result.report.contradiction_summary:
                unresolved.append(f"Discrepancy: {disc.message}")
        if decision.risk_level == ControllerRiskLevel.CRITICAL:
            unresolved.append("CRITICAL: Severe contradiction blocks automated ledger posting.")
        elif decision.decision == ControllerActionType.REVIEW_CASE:
            unresolved.append("Disambiguation required for candidate transactions.")

        # Contradictions
        contradictions: List[Dict[str, Any]] = []
        if result.report and result.report.contradiction_summary:
            contradictions = [
                {
                    "id": d.discrepancy_id,
                    "type": d.discrepancy_type,
                    "severity": d.severity,
                    "message": d.message,
                    "expected": d.expected_value,
                    "observed": d.observed_value,
                }
                for d in result.report.contradiction_summary
            ]

        # Evidence Summary
        ev_summary: List[Dict[str, Any]] = []
        if result.report and result.report.evidence_summary:
            ev_summary = [e.model_dump() if hasattr(e, "model_dump") else dict(e) for e in result.report.evidence_summary]

        # Risk Summary
        risk_summary = f"Risk evaluated as {decision.risk_level.value}. " + (
            "Manual review is REQUIRED." if decision.requires_human_review else "Zero discrepancies; automated posting approved."
        )

        # Confidence Summary
        conf_summary = f"Reconciliation confidence is {decision.confidence * 100:.0f}%. " + (
            "Derived from 100% exact multi-signal match." if decision.confidence == 1.0 else "; ".join(decision.uncertainty_reasons) or "Partial uncertainty detected."
        )

        return ControllerBrief(
            case_id=result.case_id,
            executive_summary=exec_summary,
            financial_summary=result.financial_summary or {},
            risk_summary=risk_summary,
            unresolved_items=unresolved,
            contradictions=contradictions,
            recommended_actions=decision.recommended_actions,
            confidence_summary=conf_summary,
            evidence_summary=ev_summary,
            controller_decision=decision,
        )

    def explain_query(
        self,
        result: CaseProcessingResult,
        question: str,
    ) -> ControllerExplainResponse:
        """Answers natural-language controller queries using strictly deterministic grounding facts."""
        decision = self.analyze_case(result)
        return ControllerExplainabilityEngine.answer_query(question, decision, result)
