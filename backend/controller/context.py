"""Compact structured context builder for Controller AI and explainability."""

from __future__ import annotations

from typing import Any, Dict, List, Set
from backend.case_processing.result import CaseProcessingResult
from backend.controller.models import ControllerDecision


def build_controller_ai_context(
    result: CaseProcessingResult,
    decision: ControllerDecision,
) -> Dict[str, Any]:
    """Extracts a sanitized, grounded facts dictionary for AI explanation and validation."""
    fin_sum = result.financial_summary or {}
    
    # Collect all known numbers/amounts in the deterministic facts
    known_amounts: Set[float] = set()
    if fin_sum.get("claimed_amount") is not None:
        known_amounts.add(float(fin_sum["claimed_amount"]))
    if fin_sum.get("matched_amount") is not None:
        known_amounts.add(float(fin_sum["matched_amount"]))
    if fin_sum.get("outstanding_amount") is not None:
        known_amounts.add(float(fin_sum["outstanding_amount"]))

    discrepancies_list = []
    if result.report and result.report.contradiction_summary:
        for disc in result.report.contradiction_summary:
            if disc.expected_value:
                try:
                    known_amounts.add(float(disc.expected_value))
                except ValueError:
                    pass
            if disc.observed_value:
                try:
                    known_amounts.add(float(disc.observed_value))
                except ValueError:
                    pass
            discrepancies_list.append({
                "id": disc.discrepancy_id,
                "type": disc.discrepancy_type,
                "severity": disc.severity,
                "message": disc.message,
                "expected": disc.expected_value,
                "observed": disc.observed_value,
            })

    # Collect known entities
    known_entities: Set[str] = set()
    if result.report and result.report.entity_summary:
        if result.report.entity_summary.canonical_name:
            known_entities.add(result.report.entity_summary.canonical_name.lower())

    # Build context dictionary
    return {
        "case_id": decision.case_id,
        "status": result.status,
        "confidence": decision.confidence,
        "risk_level": decision.risk_level.value,
        "primary_action": decision.decision.value,
        "requires_human_review": decision.requires_human_review,
        "reasons": decision.reasons,
        "financial_summary": fin_sum,
        "discrepancies": discrepancies_list,
        "known_amounts": list(known_amounts),
        "known_entities": list(known_entities),
        "grounding_ids": list(set(
            decision.supporting_discrepancy_ids
            + decision.supporting_claim_ids
            + decision.supporting_transaction_ids
            + decision.supporting_evidence_ids
        )),
    }
