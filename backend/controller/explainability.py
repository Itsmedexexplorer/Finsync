"""Deterministic Explainability Engine and Grounded Question Answering for VERITY."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from backend.case_processing.result import CaseProcessingResult
from backend.controller.models import (
    ControllerDecision,
    ControllerExplainResponse,
    ControllerRiskLevel,
)


class ControllerExplainabilityEngine:
    """Produces evidence-grounded rationales and answers natural-language controller queries."""

    @classmethod
    def generate_executive_summary(
        cls,
        decision: ControllerDecision,
        result: CaseProcessingResult,
    ) -> str:
        """Generates a concise, deterministic executive summary for the finance controller brief."""
        cid = decision.case_id
        status = result.status
        conf_pct = round(decision.confidence * 100)
        risk = decision.risk_level.value
        fin_sum = result.financial_summary or {}
        matched_amt = fin_sum.get("matched_amount", 0.0)
        out_amt = fin_sum.get("outstanding_amount", 0.0)

        if decision.risk_level in (ControllerRiskLevel.NONE, ControllerRiskLevel.LOW) and status == "CONFIRMED":
            return (
                f"Financial case '{cid}' is CONFIRMED with {conf_pct}% confidence and LOW risk. "
                f"A total of INR {matched_amt:,.2f} has been fully reconciled across matching evidence records with zero discrepancies."
            )

        if decision.risk_level == ControllerRiskLevel.CRITICAL:
            disc_reasons = "; ".join(decision.reasons[:2]) if decision.reasons else "Critical contradictions detected"
            return (
                f"CRITICAL RISK: Financial case '{cid}' has been halted due to severe discrepancy rules: {disc_reasons}. "
                f"Manual controller intervention is required before any ledger posting."
            )

        if status == "AMBIGUOUS":
            return (
                f"HIGH RISK: Case '{cid}' contains AMBIGUOUS candidate transactions. "
                f"Reconciliation confidence is limited to {conf_pct}%. Controller review is needed to verify the correct settlement source."
            )

        if status in ("PARTIAL", "PARTIALLY_SETTLED"):
            return (
                f"MEDIUM RISK: Case '{cid}' is PARTIALLY SETTLED. Matched amount is INR {matched_amt:,.2f} "
                f"with an outstanding balance of INR {out_amt:,.2f} requiring collections follow-up."
            )

        if status == "UNMATCHED":
            return (
                f"MEDIUM RISK: Standalone bank transaction of INR {matched_amt:,.2f} in case '{cid}' "
                f"does not correspond to any registered invoice or claim. Controller allocation required."
            )

        if status == "UNVERIFIABLE":
            return (
                f"MEDIUM RISK: Informal payment claim in case '{cid}' cannot be verified against banking ledgers. "
                f"Additional documentation (bank statement or payment receipt) is required."
            )

        return (
            f"Case '{cid}' is in status {status} (Risk: {risk}, Confidence: {conf_pct}%). "
            f"Requires human review: {'YES' if decision.requires_human_review else 'NO'}."
        )

    @classmethod
    def answer_query(
        cls,
        question: str,
        decision: ControllerDecision,
        result: CaseProcessingResult,
    ) -> ControllerExplainResponse:
        """Answers natural-language controller queries using strictly deterministic grounding facts."""
        q_lower = (question or "").lower()
        cid = decision.case_id
        grounding_ids: List[str] = []
        answer: str = ""

        # Collect all active domain IDs
        grounding_ids.extend(decision.supporting_discrepancy_ids)
        grounding_ids.extend(decision.supporting_claim_ids)
        grounding_ids.extend(decision.supporting_transaction_ids)
        grounding_ids.extend(decision.supporting_evidence_ids)

        fin_sum = result.financial_summary or {}
        matched_amt = fin_sum.get("matched_amount", 0.0)
        out_amt = fin_sum.get("outstanding_amount", 0.0)

        discrepancies = []
        if result.report and result.report.contradiction_summary:
            discrepancies = result.report.contradiction_summary

        if any(k in q_lower for k in ["why", "review", "manual", "attention"]):
            if decision.requires_human_review:
                reasons_str = "\n".join(f"• {r}" for r in decision.reasons)
                answer = (
                    f"Human review is required for case '{cid}' (Risk Level: {decision.risk_level.value}) "
                    f"because the deterministic engine detected the following issues:\n{reasons_str}"
                )
            else:
                answer = (
                    f"Case '{cid}' does NOT require human review. All claims and bank transactions "
                    f"matched cleanly with 100% confidence."
                )

        elif any(k in q_lower for k in ["risk", "biggest risk", "threat", "danger"]):
            if decision.risk_level in (ControllerRiskLevel.CRITICAL, ControllerRiskLevel.HIGH):
                top_disc = decision.reasons[0] if decision.reasons else "Active discrepancies"
                answer = (
                    f"The highest priority risk is evaluated at {decision.risk_level.value} level: {top_disc}. "
                    f"Primary recommended action is {decision.decision.value}."
                )
            else:
                answer = f"The evaluated risk level is {decision.risk_level.value} with no critical blocking anomalies."

        elif any(k in q_lower for k in ["contradiction", "discrepanc", "conflict", "mismatch"]):
            if discrepancies:
                disc_details = "\n".join(
                    f"• [{d.discrepancy_type}] {d.message} (Expected: {d.expected_value or 'N/A'}, Observed: {d.observed_value or 'N/A'})"
                    for d in discrepancies
                )
                answer = f"Found {len(discrepancies)} deterministic discrepancy record(s):\n{disc_details}"
            else:
                answer = "No contradictions or discrepancies were detected in this financial case."

        elif any(k in q_lower for k in ["unresolved", "outstanding", "balance", "how much"]):
            answer = (
                f"Financial balance summary for case '{cid}':\n"
                f"• Verified Matched Amount: INR {matched_amt:,.2f}\n"
                f"• Outstanding Balance: INR {out_amt:,.2f}\n"
                f"• Reconciliation Status: {result.status}"
            )

        elif any(k in q_lower for k in ["evidence", "verify", "document", "proof"]):
            if decision.recommended_actions:
                top_act = decision.recommended_actions[0]
                answer = (
                    f"Recommended verification step: '{top_act.title}'. "
                    f"Rationale: {top_act.rationale}. Supporting IDs: {', '.join(top_act.supporting_ids) or 'N/A'}."
                )
            else:
                answer = "All supporting evidence documents (invoices, statements, receipts) have been verified."

        else:
            # General fallback overview
            answer = (
                f"Case '{cid}' Overview:\n"
                f"• Status: {result.status}\n"
                f"• Controller Risk: {decision.risk_level.value}\n"
                f"• Human Review Required: {'YES' if decision.requires_human_review else 'NO'}\n"
                f"• Primary Action: {decision.decision.value}\n"
                f"• Matched: INR {matched_amt:,.2f} | Outstanding: INR {out_amt:,.2f}"
            )

        return ControllerExplainResponse(
            case_id=cid,
            question=question or "Case Explanation",
            answer=answer,
            grounding_ids=list(set(grounding_ids)),
            confidence=decision.confidence,
            fallback_used=True,
        )
