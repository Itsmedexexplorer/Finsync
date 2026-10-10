"""Deterministic Financial Reconciliation Engine for VERITY.

Synthesizes final, verified financial conclusions by integrating Claims, Transactions,
Resolved Entities, Match Relationships, Deduplication Groups, and Discrepancies.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Set

from backend.deduplication.result import DeduplicationGroup, DeduplicationStatus
from backend.domain.claim import Claim, ClaimType
from backend.domain.discrepancy import Discrepancy, DiscrepancySeverity
from backend.domain.entity import Entity
from backend.domain.evidence import Evidence
from backend.domain.reconciliation import MatchType, ReconciliationRecord, ReconciliationStatus
from backend.domain.transaction import Transaction, TransactionDirection
from backend.provenance.tracker import ProvenanceTracker
from backend.reconciliation.confidence import ConfidenceCalculator
from backend.reconciliation.config import ReconciliationConfig
from backend.reconciliation.result import BatchReconciliationResult, ReconciliationResult
from backend.reconciliation.rules import ReconciliationRuleEngine
from backend.transaction_matching.result import MatchRelationship, MatchRelationshipType


class ReconciliationEngine:
    """Core modular and deterministic reconciliation engine."""

    def __init__(
        self,
        config: Optional[ReconciliationConfig] = None,
        provenance_tracker: Optional[ProvenanceTracker] = None,
    ) -> None:
        self.config = config or ReconciliationConfig()
        self.tracker = provenance_tracker or ProvenanceTracker()

    def reconcile(
        self,
        claims: List[Claim],
        transactions: List[Transaction],
        evidence_items: Optional[List[Evidence]] = None,
        deduplication_groups: Optional[List[DeduplicationGroup]] = None,
        match_relationships: Optional[List[MatchRelationship]] = None,
        discrepancies: Optional[List[Discrepancy]] = None,
        claim_entity_map: Optional[Dict[str, str]] = None,
    ) -> BatchReconciliationResult:
        """Executes full reconciliation pipeline across all event groups and transactions."""
        ev_list = evidence_items or []
        dedup_list = deduplication_groups or []
        match_rels = match_relationships or []
        discs = discrepancies or []
        entity_map = claim_entity_map or {}

        # Register provenance
        for ev in ev_list:
            self.tracker.track_evidence(ev)
        for c in claims:
            self.tracker.track_claim(c)
        for t in transactions:
            self.tracker.track_transaction(t)
        for d in discs:
            self.tracker.track_discrepancy(d)

        claim_by_id = {c.id: c for c in claims}
        txn_by_id = {t.id: t for t in transactions}
        ev_by_id = {e.id: e for e in ev_list}

        results: List[ReconciliationResult] = []

        # -------------------------------------------------------------
        # Case A: Event Groups provided via Day 6 Deduplication
        # -------------------------------------------------------------
        if dedup_list:
            for grp in dedup_list:
                grp_claims = [claim_by_id[cid] for cid in grp.member_claim_ids if cid in claim_by_id]
                grp_txns = [txn_by_id[tid] for tid in grp.candidate_transaction_ids if tid in txn_by_id]
                grp_ev_ids = list(set(grp.member_evidence_ids))

                # Identify match relationships for this group
                grp_match_rels = [
                    m for m in match_rels
                    if any(cid in grp.member_claim_ids for cid in m.source_claim_ids)
                    or any(tid in grp.candidate_transaction_ids for tid in m.target_transaction_ids)
                ]

                # Identify discrepancies for this group
                grp_discs = [
                    d for d in discs
                    if any(cid in grp.member_claim_ids for cid in d.involved_claim_ids)
                    or any(tid in grp.candidate_transaction_ids for tid in d.involved_transaction_ids)
                ]

                res = self._reconcile_single_event(
                    event_id=grp.group_id,
                    claims=grp_claims,
                    transactions=grp_txns,
                    evidence_ids=grp_ev_ids,
                    match_relationships=grp_match_rels,
                    discrepancies=grp_discs,
                    claim_entity_map=entity_map,
                    dedup_group=grp,
                )
                results.append(res)
                self.tracker.track_reconciliation(res.to_domain_record(grp_discs))

        # -------------------------------------------------------------
        # Case B: Direct Evaluation (Standalone case)
        # -------------------------------------------------------------
        else:
            ev_ids = [e.id for e in ev_list]
            res = self._reconcile_single_event(
                event_id="REC-EVT-001",
                claims=claims,
                transactions=transactions,
                evidence_ids=ev_ids,
                match_relationships=match_rels,
                discrepancies=discs,
                claim_entity_map=entity_map,
            )
            results.append(res)
            self.tracker.track_reconciliation(res.to_domain_record(discs))

        # Summary Metrics
        tot_reconciled = sum(r.matched_amount for r in results)
        tot_outstanding = sum(r.outstanding_amount for r in results)
        status_dist: Dict[str, int] = {}
        for r in results:
            status_dist[r.status.value] = status_dist.get(r.status.value, 0) + 1

        return BatchReconciliationResult(
            results=results,
            total_reconciled_amount=round(tot_reconciled, 2),
            total_outstanding_amount=round(tot_outstanding, 2),
            status_counts=status_dist,
            summary_metrics={
                "total_events_reconciled": len(results),
                "claims_count": len(claims),
                "transactions_count": len(transactions),
            },
        )

    def _reconcile_single_event(
        self,
        event_id: str,
        claims: List[Claim],
        transactions: List[Transaction],
        evidence_ids: List[str],
        match_relationships: List[MatchRelationship],
        discrepancies: List[Discrepancy],
        claim_entity_map: Dict[str, str],
        dedup_group: Optional[DeduplicationGroup] = None,
    ) -> ReconciliationResult:
        """Evaluates a single financial event context and determines monetary values and status."""
        rec_id = f"REC-{uuid.uuid4().hex[:8]}"

        # 1. Determine entity
        entity_id: Optional[str] = None
        for c in claims:
            if c.id in claim_entity_map:
                entity_id = claim_entity_map[c.id]
                break
        if not entity_id:
            for t in transactions:
                entity_id = t.origin_entity_id or t.destination_entity_id
                if entity_id:
                    break

        # 2. Determine Expected Amount (Invoiced or Claimed total)
        expected_amt: Optional[float] = None
        has_amount_discrepancy = any(
            getattr(d, "discrepancy_type", "") in ("AMOUNT_MISMATCH", "CONFLICTING_CLAIMS")
            for d in discrepancies
        )
        if dedup_group and dedup_group.status in (DeduplicationStatus.SAME_EVENT, DeduplicationStatus.DUPLICATE_EVIDENCE_CONTENT) and not has_amount_discrepancy:
            if dedup_group.status == DeduplicationStatus.DUPLICATE_EVIDENCE_CONTENT:
                # Exact duplicate evidence content represents a single duplicated obligation
                valid_claim_amts = [c.claimed_amount for c in claims if c.claimed_amount is not None]
                if valid_claim_amts:
                    expected_amt = round(max(valid_claim_amts), 2)
            else:
                # SAME_EVENT: claims describe the same underlying financial event without amount contradiction
                # Prefer INVOICE_ISSUED claims representing the actual obligation(s)
                invoice_claims = [c.claimed_amount for c in claims if c.claimed_amount is not None and c.claim_type == ClaimType.INVOICE_ISSUED]
                if invoice_claims:
                    expected_amt = round(sum(invoice_claims), 2)
                else:
                    valid_claim_amts = [c.claimed_amount for c in claims if c.claimed_amount is not None]
                    if valid_claim_amts:
                        expected_amt = round(max(valid_claim_amts), 2)
        else:
            valid_claim_amts = [c.claimed_amount for c in claims if c.claimed_amount is not None]
            if valid_claim_amts:
                expected_amt = round(sum(valid_claim_amts), 2)
            elif match_relationships:
                expected_amt = round(match_relationships[0].target_amount, 2)

        # 3. Determine Matched Amount on Ledger
        matched_amt: float = 0.0
        if transactions:
            matched_amt = round(sum(t.amount for t in transactions if t.direction == TransactionDirection.CREDIT or len(transactions) == 1), 2)

        # 4. Apply Rule Hierarchy
        status, supporting_sigs, contradicting_sigs, explanation = ReconciliationRuleEngine.evaluate_status(
            claims=claims,
            transactions=transactions,
            match_relationships=match_relationships,
            discrepancies=discrepancies,
            entity_id=entity_id,
            config=self.config,
        )

        # If deduplication group indicates cryptographic duplicate, append signal
        if dedup_group and dedup_group.status == DeduplicationStatus.DUPLICATE_EVIDENCE_CONTENT:
            supporting_sigs.append("CRYPTOGRAPHIC_CONTENT_DUPLICATE")

        # 5. Calculate Outstanding Amount
        outstanding_amt: float = 0.0
        if expected_amt is not None:
            if status in (ReconciliationStatus.PARTIAL, ReconciliationStatus.PARTIALLY_SETTLED):
                outstanding_amt = max(0.0, round(expected_amt - matched_amt, 2))
            elif status == ReconciliationStatus.CONFIRMED:
                outstanding_amt = 0.0
            elif status in (ReconciliationStatus.UNVERIFIABLE, ReconciliationStatus.CONTRADICTED):
                outstanding_amt = expected_amt

        # 6. Calculate Confidence
        confidence = ConfidenceCalculator.calculate_confidence(
            status=status,
            supporting_signals=supporting_sigs,
            contradicting_signals=contradicting_sigs,
            discrepancies=discrepancies,
            evidence_count=len(evidence_ids),
        )

        return ReconciliationResult(
            reconciliation_id=rec_id,
            status=status,
            event_id=event_id,
            entity_id=entity_id,
            claim_ids=[c.id for c in claims],
            transaction_ids=[t.id for t in transactions],
            evidence_ids=evidence_ids,
            expected_amount=expected_amt,
            matched_amount=matched_amt,
            outstanding_amount=outstanding_amt,
            confidence_score=confidence,
            supporting_signals=supporting_sigs,
            contradicting_signals=contradicting_sigs,
            discrepancy_ids=[d.id for d in discrepancies],
            match_relationship_ids=[m.id for m in match_relationships],
            deduplication_group_ids=[dedup_group.group_id] if dedup_group else [],
            explanation=explanation,
            reason_codes=[status.value],
            provenance={"event_id": event_id, "evidence_count": len(evidence_ids)},
        )

    def reconcile_case(
        self,
        reconciliation_id: str,
        evidence_items: List[Evidence],
        claims: List[Claim],
        transactions: List[Transaction],
        counterparty: Optional[Entity] = None,
    ) -> ReconciliationRecord:
        """Backward-compatible interface for Day 1 case evaluation."""
        entity_map = {c.id: counterparty.id for c in claims} if counterparty else {}
        batch_res = self.reconcile(
            claims=claims,
            transactions=transactions,
            evidence_items=evidence_items,
            claim_entity_map=entity_map,
        )
        if batch_res.results:
            rec_result = batch_res.results[0]
            rec_result.reconciliation_id = reconciliation_id
            return rec_result.to_domain_record()

        # Fallback empty
        return ReconciliationRecord(
            id=reconciliation_id,
            status=ReconciliationStatus.UNVERIFIABLE,
            explanation_summary="No reconciliation result produced.",
        )
