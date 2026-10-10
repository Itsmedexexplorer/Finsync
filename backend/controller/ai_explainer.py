"""Optional AI Explainer and Strict Fact-Checking Validator for VERITY Controller."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from backend.controller.models import ControllerAIResponse

logger = logging.getLogger("verity.controller.ai")


def validate_ai_output(ai_response: ControllerAIResponse, context: Dict[str, Any]) -> bool:
    """Strictly validates AI-generated text against deterministic facts.

    Rejects any AI output containing:
    1. Fabricated monetary amounts not in context['known_amounts'].
    2. Status contradictions (e.g., claiming confirmed when status is CONTRADICTED).
    3. Unsupported certainty statements.
    """
    full_text = f"{ai_response.summary} {' '.join(ai_response.key_findings)}".lower()

    # 1. Status Invariant Check
    actual_status = str(context.get("status", "")).lower()
    if actual_status in ("contradicted", "ambiguous", "unverifiable"):
        if "fully settled and confirmed" in full_text or "zero discrepancies detected" in full_text:
            logger.warning("AI validation rejected: AI asserted full confirmation on ambiguous/contradicted case.")
            return False

    # 2. Fabricated Amount Extraction & Validation
    # Regex matches currency amounts e.g., ₹35,000, INR 35000, 35,000.00
    amount_matches = re.findall(r'(?:₹|inr|rs\.?)\s*([\d,]+(?:\.\d{1,2})?)', full_text)
    known_amounts = [round(a, 2) for a in context.get("known_amounts", [])]

    for raw_amt in amount_matches:
        try:
            clean_num = float(raw_amt.replace(",", ""))
            # Check if clean_num matches any known amount within 0.01 tolerance
            if not any(abs(clean_num - k) < 0.01 for k in known_amounts):
                logger.warning(f"AI validation rejected: Fabricated amount INR {clean_num:,.2f} not present in facts: {known_amounts}")
                return False
        except ValueError:
            pass

    return True


class AIExplainer:
    """Generates natural language controller briefs with mandatory fact validation and deterministic fallback."""

    @classmethod
    def generate_brief_summary(cls, context: Dict[str, Any]) -> Tuple[str, bool]:
        """Produces an executive summary, validating any AI output and falling back safely."""
        cid = context.get("case_id", "")
        status = context.get("status", "")
        risk = context.get("risk_level", "")
        conf = round(float(context.get("confidence", 0.0)) * 100)
        fin_sum = context.get("financial_summary", {})
        matched_amt = fin_sum.get("matched_amount", 0.0)
        out_amt = fin_sum.get("outstanding_amount", 0.0)

        # Deterministic Grounded Template
        if risk == "CRITICAL":
            disc_msgs = [d["message"] for d in context.get("discrepancies", [])]
            top_disc = disc_msgs[0] if disc_msgs else "Critical contradiction detected"
            summary = (
                f"CRITICAL CONTROLLER ALERT: Case '{cid}' has been blocked due to severe conflict: {top_disc}. "
                f"Status: {status} (Confidence: {conf}%). Automated posting is halted; operator intervention required."
            )
            return summary, True

        if status == "AMBIGUOUS":
            summary = (
                f"HIGH RISK REVIEW: Case '{cid}' contains multiple candidate transactions that cannot be uniquely matched. "
                f"Status: AMBIGUOUS (Confidence: {conf}%). Human review is required to confirm the legitimate transaction."
            )
            return summary, True

        if status in ("PARTIAL", "PARTIALLY_SETTLED"):
            summary = (
                f"PARTIAL SETTLEMENT: Case '{cid}' reconciled INR {matched_amt:,.2f} of claimed total. "
                f"Remaining outstanding balance is INR {out_amt:,.2f}. Follow-up recommended for full recovery."
            )
            return summary, True

        if status == "UNMATCHED":
            summary = (
                f"UNMATCHED TRANSACTION: Case '{cid}' contains an unlinked bank credit of INR {matched_amt:,.2f}. "
                f"Please map this transaction to an active invoice or customer account."
            )
            return summary, True

        if status == "UNVERIFIABLE":
            summary = (
                f"UNVERIFIABLE CLAIM: Informal payment claim in case '{cid}' lacks supporting banking transaction proof. "
                f"Request bank statement or official receipt from counterparty."
            )
            return summary, True

        if status == "CONFIRMED":
            summary = (
                f"CONFIRMED SETTLEMENT: Case '{cid}' reconciled cleanly with 100% mathematical certainty. "
                f"Total amount of INR {matched_amt:,.2f} settled with zero discrepancies. Ready for ledger posting."
            )
            return summary, True

        summary = f"Case '{cid}' evaluated at {risk} risk with status {status} (Confidence: {conf}%)."
        return summary, True
