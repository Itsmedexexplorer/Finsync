"""Deterministic Financial Reconciliation Rule Engine for VERITY."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from backend.domain.claim import Claim, ClaimType
from backend.domain.discrepancy import Discrepancy, DiscrepancySeverity, DiscrepancyType
from backend.domain.reconciliation import ReconciliationStatus
from backend.domain.transaction import Transaction
from backend.reconciliation.config import ReconciliationConfig
from backend.transaction_matching.result import MatchRelationship, MatchRelationshipType, MatchStatus


class ReconciliationRuleEngine:
    """Evaluates deterministic rules to synthesize verified financial reconciliation conclusions."""

    @classmethod
    def evaluate_status(
        cls,
        claims: List[Claim],
        transactions: List[Transaction],
        match_relationships: Optional[List[MatchRelationship]] = None,
        discrepancies: Optional[List[Discrepancy]] = None,
        entity_id: Optional[str] = None,
        config: Optional[ReconciliationConfig] = None,
    ) -> Tuple[ReconciliationStatus, List[str], List[str], str]:
        """Applies deterministic rule hierarchy to determine final reconciliation status."""
        cfg = config or ReconciliationConfig()
        discs = discrepancies or []
        match_rels = match_relationships or []

        supporting_signals: List[str] = []
        contradicting_signals: List[str] = []
        reasons: List[str] = []

        # -----------------------------------------------------------------
        # Priority 1: Contradiction Dominance (RULE_RECON_004)
        # Material Day 7 contradictions strictly prevent CONFIRMED status
        # -----------------------------------------------------------------
        material_discs = [
            d for d in discs
            if d.discrepancy_type in (
                DiscrepancyType.AMOUNT_MISMATCH,
                DiscrepancyType.REFERENCE_MISMATCH,
                DiscrepancyType.ENTITY_MISMATCH,
                DiscrepancyType.DIRECTION_MISMATCH,
                DiscrepancyType.CONFLICTING_CLAIMS,
            )
            or d.severity in (DiscrepancySeverity.CRITICAL, DiscrepancySeverity.ERROR)
        ]

        if material_discs:
            contradicting_signals.extend([d.discrepancy_type.value for d in material_discs])
            reasons.append(f"RULE_RECON_004 (Contradiction Dominance): {len(material_discs)} material contradiction(s) detected: {'; '.join(d.message for d in material_discs)}.")
            return (ReconciliationStatus.CONTRADICTED, supporting_signals, contradicting_signals, "; ".join(reasons))

        # Check if MatchRelationship itself was flagged as CONFLICTING
        if any(m.status == MatchStatus.CONFLICTING for m in match_rels):
            contradicting_signals.append("MATCH_RELATIONSHIP_CONFLICT")
            reasons.append("RULE_RECON_004: Transaction match relationship contains unresolved conflicts.")
            return (ReconciliationStatus.CONTRADICTED, supporting_signals, contradicting_signals, "; ".join(reasons))

        # -----------------------------------------------------------------
        # Priority 2: Ambiguity Preservation (RULE_RECON_007)
        # -----------------------------------------------------------------
        if any(m.status == MatchStatus.AMBIGUOUS for m in match_rels):
            supporting_signals.append("AMBIGUOUS_CANDIDATES")
            reasons.append("RULE_RECON_007: Multiple competing candidates exist with close confidence scores. Preserving ambiguity for human review.")
            return (ReconciliationStatus.AMBIGUOUS, supporting_signals, contradicting_signals, "; ".join(reasons))

        # -----------------------------------------------------------------
        # Priority 3: Missing Information / Unverifiable Claims (RULE_RECON_005)
        # -----------------------------------------------------------------
        if claims and not transactions:
            # Claims exist without any bank ledger proof
            has_unstated_amount = any(c.claimed_amount is None for c in claims)
            if has_unstated_amount:
                reasons.append("RULE_RECON_005: Unsubstantiated claim with unstated amount lacking ledger transaction backing.")
            else:
                reasons.append("RULE_RECON_005: Financial claim lacks supporting bank ledger transaction.")
            return (ReconciliationStatus.UNVERIFIABLE, supporting_signals, contradicting_signals, "; ".join(reasons))

        # -----------------------------------------------------------------
        # Priority 4: Unmatched Ledger Transactions (RULE_RECON_006)
        # -----------------------------------------------------------------
        if transactions and not claims and not match_rels:
            reasons.append("RULE_RECON_006: Standalone ledger transaction without matching invoice, obligation, or claim.")
            return (ReconciliationStatus.UNMATCHED, supporting_signals, contradicting_signals, "; ".join(reasons))

        # -----------------------------------------------------------------
        # Priority 5: Partial Settlement (RULE_RECON_003)
        # -----------------------------------------------------------------
        is_partial = any(m.relationship_type == MatchRelationshipType.PARTIAL for m in match_rels)
        if is_partial and cfg.allow_partial_settlement:
            supporting_signals.append("VALID_PARTIAL_PAYMENT")
            if entity_id:
                supporting_signals.append("EXACT_ENTITY")
            reasons.append("RULE_RECON_003 (Partial Settlement): Valid partial payment verified against expected obligation.")
            return (ReconciliationStatus.PARTIALLY_SETTLED, supporting_signals, contradicting_signals, "; ".join(reasons))

        # -----------------------------------------------------------------
        # Priority 6: Many-to-One and One-to-Many Settlement (RULE_RECON_009, 010)
        # -----------------------------------------------------------------
        m2o = [m for m in match_rels if m.relationship_type == MatchRelationshipType.MANY_TO_ONE]
        if m2o:
            supporting_signals.extend(["MANY_TO_ONE_SUM_MATCH", "SUM_AMOUNT_MATCH", "MATCHED_RELATIONSHIP"])
            if entity_id:
                supporting_signals.append("EXACT_ENTITY")
            reasons.append(f"RULE_RECON_009 (Many-to-One Settlement): Multiple milestone transactions ({len(transactions)}) sum to exact invoice total.")
            return (ReconciliationStatus.CONFIRMED, supporting_signals, contradicting_signals, "; ".join(reasons))

        o2m = [m for m in match_rels if m.relationship_type == MatchRelationshipType.ONE_TO_MANY]
        if o2m:
            supporting_signals.extend(["ONE_TO_MANY_SUM_MATCH", "SUM_AMOUNT_MATCH", "MATCHED_RELATIONSHIP"])
            if entity_id:
                supporting_signals.append("EXACT_ENTITY")
            reasons.append(f"RULE_RECON_010 (One-to-Many Settlement): Bulk payment settles multiple ({len(claims)}) invoices.")
            return (ReconciliationStatus.CONFIRMED, supporting_signals, contradicting_signals, "; ".join(reasons))

        # -----------------------------------------------------------------
        # Priority 7: Exact & Reference-Backed Confirmation (RULE_RECON_001, 002)
        # -----------------------------------------------------------------
        if match_rels and any(m.status == MatchStatus.MATCHED for m in match_rels):
            supporting_signals.extend(["MATCHED_RELATIONSHIP", "EXACT_AMOUNT"])
            if entity_id:
                supporting_signals.append("EXACT_ENTITY")
            if any("EXACT_REFERENCE" in m.matched_signals for m in match_rels):
                supporting_signals.append("EXACT_REFERENCE")

            reasons.append("RULE_RECON_001 / RULE_RECON_002: Obligation fully corroborated by verified ledger transaction, reference, and entity match.")
            return (ReconciliationStatus.CONFIRMED, supporting_signals, contradicting_signals, "; ".join(reasons))

        # Direct verification when claims and transactions match exactly
        if claims and transactions:
            total_c = sum(c.claimed_amount or 0.0 for c in claims if c.claimed_amount is not None)
            total_t = sum(t.amount for t in transactions)

            if abs(total_c - total_t) <= cfg.amount_tolerance_abs and total_t > 0:
                supporting_signals.append("EXACT_AMOUNT")
                if entity_id:
                    supporting_signals.append("EXACT_ENTITY")
                reasons.append("RULE_RECON_001: Verified credit on ledger matches expected obligation.")
                return (ReconciliationStatus.CONFIRMED, supporting_signals, contradicting_signals, "; ".join(reasons))

        # Fallback
        reasons.append("Unreconciled evidence without verified ledger match.")
        return (ReconciliationStatus.UNVERIFIABLE, supporting_signals, contradicting_signals, "; ".join(reasons))
