"""Deterministic Explainability Engine for VERITY Financial Truth Reporting.

Generates structured explanations, confidence factor breakdowns, and recommended actions
strictly from verified domain facts without using LLMs or hallucinating information.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.domain.claim import Claim
from backend.domain.discrepancy import Discrepancy, DiscrepancySeverity, DiscrepancyType
from backend.domain.entity import Entity
from backend.domain.evidence import Evidence
from backend.domain.reconciliation import ReconciliationStatus
from backend.domain.transaction import Transaction
from backend.reconciliation.result import ReconciliationResult
from backend.reporting.models import ConfidenceFactor, ReportStatus, UnresolvedItem
from backend.transaction_matching.result import MatchRelationship, MatchRelationshipType, MatchStatus


class ExplainabilityEngine:
    """Deterministic explanation builder for financial truth reports."""

    @classmethod
    def generate_title(
        cls,
        status: ReconciliationStatus,
        expected_amount: Optional[float],
        matched_amount: float,
        entity_name: str,
    ) -> str:
        """Generates a concise human-readable title."""
        amt_str = f"INR {expected_amount:,.2f}" if expected_amount is not None else f"INR {matched_amount:,.2f}"
        if status == ReconciliationStatus.CONFIRMED:
            return f"Confirmed Settlement of {amt_str} for {entity_name}"
        elif status in (ReconciliationStatus.PARTIAL, ReconciliationStatus.PARTIALLY_SETTLED):
            return f"Partial Settlement ({amt_str}) for {entity_name}"
        elif status == ReconciliationStatus.CONTRADICTED:
            return f"Contradiction Detected on {amt_str} Settlement for {entity_name}"
        elif status == ReconciliationStatus.AMBIGUOUS:
            return f"Ambiguous Settlement Candidates for {entity_name}"
        elif status == ReconciliationStatus.UNVERIFIABLE:
            return f"Unverifiable Financial Claim for {entity_name}"
        elif status == ReconciliationStatus.UNMATCHED:
            return f"Unmatched Ledger Credit of INR {matched_amount:,.2f}"
        return f"Financial Reconciliation Case for {entity_name}"

    @classmethod
    def generate_executive_summary(
        cls,
        status: ReconciliationStatus,
        expected_amount: Optional[float],
        matched_amount: float,
        outstanding_amount: float,
        entity_name: str,
        discrepancies: List[Discrepancy],
    ) -> str:
        """Generates an executive summary of the financial conclusion."""
        if status == ReconciliationStatus.CONFIRMED:
            exp_str = f"INR {expected_amount:,.2f}" if expected_amount is not None else f"INR {matched_amount:,.2f}"
            return f"VERITY has fully confirmed the financial settlement of {exp_str} associated with {entity_name}. The expected obligation matches verified bank ledger records with zero unresolved contradictions."

        elif status in (ReconciliationStatus.PARTIAL, ReconciliationStatus.PARTIALLY_SETTLED):
            return f"VERITY verified a partial settlement of INR {matched_amount:,.2f} against the expected obligation of INR {expected_amount:,.2f} for {entity_name}. An outstanding balance of INR {outstanding_amount:,.2f} remains unsettled."

        elif status == ReconciliationStatus.CONTRADICTED:
            reasons = [d.message for d in discrepancies] if discrepancies else ["Material discrepancies detected between claims and bank records."]
            return f"VERITY identified financial contradictions that prevent reconciliation for {entity_name}. Core disagreement: {'; '.join(reasons)}"

        elif status == ReconciliationStatus.AMBIGUOUS:
            return f"VERITY identified multiple competing transaction candidates for {entity_name}. Financial truth cannot be safely resolved without human disambiguation."

        elif status == ReconciliationStatus.UNVERIFIABLE:
            return f"VERITY could not corroborate the financial claim for {entity_name} due to missing bank ledger transactions or unstated claim amounts."

        elif status == ReconciliationStatus.UNMATCHED:
            return f"VERITY verified an unmatched bank ledger credit of INR {matched_amount:,.2f} that has no corresponding invoice, obligation, or counterparty claim."

        return f"Financial reconciliation evaluated with status {status.value}."

    @classmethod
    def generate_detailed_explanation(
        cls,
        reconciliation_result: ReconciliationResult,
        claims: List[Claim],
        transactions: List[Transaction],
        evidence: List[Evidence],
        discrepancies: List[Discrepancy],
        entity: Optional[Entity] = None,
        match_relationship: Optional[MatchRelationship] = None,
    ) -> str:
        """Generates a deep, deterministic paragraph explaining WHY the conclusion was reached."""
        lines: List[str] = []
        status = reconciliation_result.status
        entity_name = entity.canonical_name if entity else (claims[0].counterparty_hint if claims and claims[0].counterparty_hint else "Unknown Entity")

        if status == ReconciliationStatus.CONFIRMED:
            lines.append(f"Full financial reconciliation was confirmed for {entity_name}.")
            if match_relationship and match_relationship.relationship_type == MatchRelationshipType.MANY_TO_ONE:
                lines.append(f"The total obligation of INR {reconciliation_result.expected_amount:,.2f} was substantiated across {len(transactions)} verified milestone bank transactions summing to exact parity.")
            elif match_relationship and match_relationship.relationship_type == MatchRelationshipType.ONE_TO_MANY:
                lines.append(f"A single bulk ledger transaction of INR {reconciliation_result.matched_amount:,.2f} settled {len(claims)} individual invoices without double-counting.")
            else:
                lines.append(f"The expected amount of INR {reconciliation_result.matched_amount:,.2f} was corroborated by bank ledger transaction ({transactions[0].bank_reference or transactions[0].id if transactions else 'verified'}) matching the claim.")
            if len(evidence) > 1:
                modalities = {e.modality.value for e in evidence}
                lines.append(f"Evidence provenance is strengthened by {len(evidence)} cross-modal artifacts ({', '.join(sorted(modalities))}).")
            lines.append("No material discrepancies or conflicting signals were detected.")

        elif status in (ReconciliationStatus.PARTIAL, ReconciliationStatus.PARTIALLY_SETTLED):
            exp = reconciliation_result.expected_amount or 0.0
            rec = reconciliation_result.matched_amount
            out = reconciliation_result.outstanding_amount
            lines.append(f"A valid partial payment relationship was established for {entity_name}.")
            lines.append(f"The original obligation was INR {exp:,.2f}, and verified ledger credits equal INR {rec:,.2f}.")
            lines.append(f"Because the settlement relationship is partial, VERITY computed the remaining outstanding balance of INR {out:,.2f} rather than flagging an amount contradiction.")

        elif status == ReconciliationStatus.CONTRADICTED:
            lines.append(f"VERITY could not confirm settlement for {entity_name} due to material evidence contradictions.")
            for d in discrepancies:
                lines.append(f"Contradiction [{d.discrepancy_type.value}]: {d.message}")
                if d.expected_value and d.observed_value:
                    lines.append(f"Expected value '{d.expected_value}' contradicts observed ledger value '{d.observed_value}'.")
            lines.append("Per the Contradiction Dominance rule (RULE_RECON_004), unresolved contradictions strictly override similarity matching.")

        elif status == ReconciliationStatus.AMBIGUOUS:
            lines.append(f"Reconciliation for {entity_name} is ambiguous because multiple candidate transactions or claims exist with equal plausibility.")
            lines.append("VERITY explicitly avoids arbitrary tie-breaking to prevent incorrect accounting merges.")

        elif status == ReconciliationStatus.UNVERIFIABLE:
            lines.append(f"The financial assertion for {entity_name} is unverifiable.")
            if any(c.claimed_amount is None for c in claims):
                lines.append("The claim lacked a stated monetary amount (e.g. 'I sent the money').")
            if not transactions:
                lines.append("No corresponding bank ledger transaction was found to corroborate the claim.")

        elif status == ReconciliationStatus.UNMATCHED:
            amt = reconciliation_result.matched_amount
            lines.append(f"A verified bank transaction of INR {amt:,.2f} was recorded on the ledger, but no matching invoice, contract, or claim was provided in the evidence corpus.")

        return " ".join(lines)

    @classmethod
    def generate_confidence_breakdown(
        cls,
        reconciliation_result: ReconciliationResult,
        evidence: List[Evidence],
        discrepancies: List[Discrepancy],
        match_relationship: Optional[MatchRelationship] = None,
    ) -> List[ConfidenceFactor]:
        """Generates list of explainable positive and negative confidence factors."""
        factors: List[ConfidenceFactor] = []
        sigs = reconciliation_result.supporting_signals

        if "EXACT_REFERENCE" in sigs:
            factors.append(ConfidenceFactor(
                factor_type="EXACT_REFERENCE",
                impact="+",
                description="Explicit bank reference (UTR/RRN) matched identically across evidence sources.",
            ))
        if "EXACT_AMOUNT" in sigs or "MANY_TO_ONE_SUM_MATCH" in sigs or "SUM_AMOUNT_MATCH" in sigs:
            factors.append(ConfidenceFactor(
                factor_type="EXACT_AMOUNT",
                impact="+",
                description="Monetary amounts matched exactly without numeric discrepancy.",
            ))
        if "EXACT_ENTITY" in sigs:
            factors.append(ConfidenceFactor(
                factor_type="EXACT_ENTITY",
                impact="+",
                description="Counterparty identity verified against canonical entity registry.",
            ))
        if len(evidence) > 1:
            factors.append(ConfidenceFactor(
                factor_type="MULTIPLE_EVIDENCE_SOURCES",
                impact="+",
                description=f"Corroborated across {len(evidence)} independent multimodal evidence items.",
            ))
        if "VALID_PARTIAL_PAYMENT" in sigs:
            factors.append(ConfidenceFactor(
                factor_type="VALID_PARTIAL_PAYMENT",
                impact="+",
                description="Recognized installment payment matching structured partial obligation.",
            ))

        # Negative factors
        for d in discrepancies:
            factors.append(ConfidenceFactor(
                factor_type=d.discrepancy_type.value,
                impact="-",
                description=d.message,
            ))
        if reconciliation_result.status == ReconciliationStatus.AMBIGUOUS:
            factors.append(ConfidenceFactor(
                factor_type="AMBIGUITY_PENALTY",
                impact="-",
                description="Multiple competing match candidates reduced certainty.",
            ))
        if reconciliation_result.status == ReconciliationStatus.UNVERIFIABLE:
            factors.append(ConfidenceFactor(
                factor_type="MISSING_INFORMATION",
                impact="-",
                description="Absence of corroborating ledger transactions or missing claim amount.",
            ))

        return factors

    @classmethod
    def generate_unresolved_items(
        cls,
        reconciliation_result: ReconciliationResult,
        discrepancies: List[Discrepancy],
    ) -> List[UnresolvedItem]:
        """Generates list of unresolved questions or anomalies."""
        items: List[UnresolvedItem] = []
        for d in discrepancies:
            items.append(UnresolvedItem(
                item_type="DISCREPANCY",
                description=f"{d.discrepancy_type.value}: {d.message}",
                severity=d.severity.value,
            ))

        if reconciliation_result.status in (ReconciliationStatus.PARTIAL, ReconciliationStatus.PARTIALLY_SETTLED):
            items.append(UnresolvedItem(
                item_type="OUTSTANDING_BALANCE",
                description=f"Remaining balance of INR {reconciliation_result.outstanding_amount:,.2f} is unsettled.",
                severity="WARNING",
            ))
        elif reconciliation_result.status == ReconciliationStatus.AMBIGUOUS:
            items.append(UnresolvedItem(
                item_type="AMBIGUOUS_CANDIDATES",
                description="Multiple plausible transactions exist; human selection is required.",
                severity="WARNING",
            ))
        elif reconciliation_result.status == ReconciliationStatus.UNVERIFIABLE:
            items.append(UnresolvedItem(
                item_type="MISSING_LEDGER_PROOF",
                description="No verified bank transaction found corresponding to the claim.",
                severity="ERROR",
            ))
        elif reconciliation_result.status == ReconciliationStatus.UNMATCHED:
            items.append(UnresolvedItem(
                item_type="UNMATCHED_TRANSACTION",
                description="Bank transaction lacks matching obligation, invoice, or claim.",
                severity="INFO",
            ))

        return items

    @classmethod
    def generate_recommended_actions(
        cls,
        status: ReconciliationStatus,
        outstanding_amount: float,
        discrepancies: List[Discrepancy],
    ) -> List[str]:
        """Generates deterministic next steps based on case status."""
        if status == ReconciliationStatus.CONFIRMED:
            return ["No immediate action required. Financial settlement is verified."]
        elif status in (ReconciliationStatus.PARTIAL, ReconciliationStatus.PARTIALLY_SETTLED):
            return [
                f"Track outstanding balance of INR {outstanding_amount:,.2f}.",
                "Await subsequent installment payments or issue payment reminder.",
            ]
        elif status == ReconciliationStatus.CONTRADICTED:
            actions = ["Review conflicting evidence sources."]
            for d in discrepancies:
                if d.discrepancy_type == DiscrepancyType.AMOUNT_MISMATCH:
                    actions.append("Audit invoice amount against bank settlement to resolve discrepancy.")
                elif d.discrepancy_type == DiscrepancyType.ENTITY_MISMATCH:
                    actions.append("Verify counterparty identity on bank statement against claimed party.")
                elif d.discrepancy_type == DiscrepancyType.REFERENCE_MISMATCH:
                    actions.append("Request corrected payment UTR/RRN receipt from counterparty.")
            return actions
        elif status == ReconciliationStatus.AMBIGUOUS:
            return [
                "Human review required to select the correct candidate transaction.",
                "Verify counterparty transaction timestamps to resolve ambiguity.",
            ]
        elif status == ReconciliationStatus.UNVERIFIABLE:
            return [
                "Request formal payment proof or bank deposit voucher from claimant.",
                "Check for pending bank statement sync or missing statement pages.",
            ]
        elif status == ReconciliationStatus.UNMATCHED:
            return [
                "Map unmatched transaction to existing customer account or create manual ledger entry.",
                "Check for missing invoice upload in system.",
            ]
        return ["Review case records."]
