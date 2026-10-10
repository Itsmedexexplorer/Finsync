"""Deterministic Contradiction Detector Engine for VERITY."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Set

from backend.contradiction_detection.config import ContradictionConfig
from backend.contradiction_detection.result import ContradictionResult
from backend.contradiction_detection.rules import ContradictionRuleEngine
from backend.deduplication.result import DeduplicationGroup, DeduplicationStatus
from backend.domain.claim import Claim, ClaimType
from backend.domain.discrepancy import Discrepancy, DiscrepancySeverity, DiscrepancyType
from backend.domain.transaction import Transaction, TransactionDirection
from backend.transaction_matching.result import MatchRelationship, MatchRelationshipType


class ContradictionDetector:
    """Core deterministic detector identifying financial disagreements and anomalies."""

    def __init__(self, config: Optional[ContradictionConfig] = None) -> None:
        self.config = config or ContradictionConfig()

    def detect(
        self,
        claims: List[Claim],
        transactions: List[Transaction],
        deduplication_groups: Optional[List[DeduplicationGroup]] = None,
        match_relationships: Optional[List[MatchRelationship]] = None,
        claim_entity_map: Optional[Dict[str, str]] = None,
    ) -> ContradictionResult:
        """Runs contradiction rules across structured financial artifacts."""
        discrepancies: List[Discrepancy] = []
        entity_map = claim_entity_map or {}
        claim_by_id = {c.id: c for c in claims}
        txn_by_id = {t.id: t for t in transactions}

        # -------------------------------------------------------------
        # 1. Contradictions from Match Relationships (Day 5 Context)
        # -------------------------------------------------------------
        if match_relationships:
            for rel in match_relationships:
                rel_claims = [claim_by_id[cid] for cid in rel.source_claim_ids if cid in claim_by_id]
                rel_txns = [txn_by_id[tid] for tid in rel.target_transaction_ids if tid in txn_by_id]

                for c in rel_claims:
                    for t in rel_txns:
                        # Check amount
                        disc_amt = ContradictionRuleEngine.check_amount_discrepancy(
                            claim=c,
                            transaction=t,
                            match_relationship=rel,
                            config=self.config,
                        )
                        if disc_amt:
                            discrepancies.append(disc_amt)

                        # Check reference
                        disc_ref = ContradictionRuleEngine.check_reference_discrepancy(
                            ref_a=c.reference_id_hint,
                            ref_b=t.bank_reference,
                            ev_ids=[c.evidence_id] + t.evidence_ids,
                            claim_ids=[c.id],
                            txn_ids=[t.id],
                        )
                        if disc_ref:
                            discrepancies.append(disc_ref)

                        # Check entity
                        c_ent = entity_map.get(c.id)
                        t_ent = t.origin_entity_id or t.destination_entity_id
                        disc_ent = ContradictionRuleEngine.check_entity_discrepancy(
                            entity_a=c_ent,
                            entity_b=t_ent,
                            ev_ids=[c.evidence_id] + t.evidence_ids,
                            claim_ids=[c.id],
                            txn_ids=[t.id],
                        )
                        if disc_ent:
                            discrepancies.append(disc_ent)

                        # Check date
                        disc_date = ContradictionRuleEngine.check_date_discrepancy(
                            date_a_str=c.claimed_date,
                            date_b_dt=t.known_timestamp,
                            ev_ids=[c.evidence_id] + t.evidence_ids,
                            claim_ids=[c.id],
                            txn_ids=[t.id],
                            config=self.config,
                        )
                        if disc_date:
                            discrepancies.append(disc_date)

                        # Check direction
                        if c.claim_type == ClaimType.PAYMENT_SENT and t.direction == TransactionDirection.DEBIT:
                            # Both represent outflow, compatible
                            pass
                        elif c.claim_type in (ClaimType.INVOICE_ISSUED, ClaimType.PAYMENT_RECEIVED) and t.direction == TransactionDirection.DEBIT:
                            # Inflow expected but debit observed on account
                            disc_dir = Discrepancy(
                                id=f"DISC-DIR-{uuid.uuid4().hex[:8]}",
                                discrepancy_type=DiscrepancyType.DIRECTION_MISMATCH,
                                severity=DiscrepancySeverity.CRITICAL,
                                message=f"Transaction direction mismatch: Expected credit inflow for {c.claim_type.value} but found debit.",
                                involved_evidence_ids=[c.evidence_id] + t.evidence_ids,
                                involved_claim_ids=[c.id],
                                involved_transaction_ids=[t.id],
                                expected_value="CREDIT",
                                observed_value="DEBIT",
                            )
                            discrepancies.append(disc_dir)

        # -------------------------------------------------------------
        # 2. Contradictions from Deduplication Groups (Day 6 Context)
        # -------------------------------------------------------------
        if deduplication_groups:
            for grp in deduplication_groups:
                grp_claims = [claim_by_id[cid] for cid in grp.member_claim_ids if cid in claim_by_id]
                # Check for conflicting claims inside the same event group
                claim_discs = ContradictionRuleEngine.check_conflicting_claims(grp_claims)
                discrepancies.extend(claim_discs)

        # -------------------------------------------------------------
        # 3. Direct Pairwise Evaluation for Unmatched/Standalone Pairs
        # -------------------------------------------------------------
        if not match_relationships:
            for c in claims:
                c_ent = entity_map.get(c.id)
                for t in transactions:
                    t_ent = t.origin_entity_id or t.destination_entity_id
                    # If references match, compare values
                    c_ref = ContradictionRuleEngine._normalize_ref(c.reference_id_hint or "")
                    t_ref = ContradictionRuleEngine._normalize_ref(t.bank_reference or "")

                    if c_ref and t_ref and c_ref == t_ref:
                        disc_amt = ContradictionRuleEngine.check_amount_discrepancy(c, t, config=self.config)
                        if disc_amt:
                            discrepancies.append(disc_amt)
                        disc_ent = ContradictionRuleEngine.check_entity_discrepancy(c_ent, t_ent, [c.evidence_id] + t.evidence_ids, [c.id], [t.id])
                        if disc_ent:
                            discrepancies.append(disc_ent)
                        disc_date = ContradictionRuleEngine.check_date_discrepancy(c.claimed_date, t.known_timestamp, [c.evidence_id] + t.evidence_ids, [c.id], [t.id], self.config)
                        if disc_date:
                            discrepancies.append(disc_date)
                    elif c_ent and t_ent and c_ent == t_ent:
                        # Same entity
                        disc_amt = ContradictionRuleEngine.check_amount_discrepancy(c, t, config=self.config)
                        if disc_amt:
                            discrepancies.append(disc_amt)
                        disc_ref = ContradictionRuleEngine.check_reference_discrepancy(c.reference_id_hint, t.bank_reference, [c.evidence_id] + t.evidence_ids, [c.id], [t.id])
                        if disc_ref:
                            discrepancies.append(disc_ref)
                        disc_date = ContradictionRuleEngine.check_date_discrepancy(c.claimed_date, t.known_timestamp, [c.evidence_id] + t.evidence_ids, [c.id], [t.id], self.config)
                        if disc_date:
                            discrepancies.append(disc_date)
                    elif c_ent and t_ent and c_ent != t_ent:
                        # Check if claim and txn were asserted in same context
                        pass

        # Deduplicate identical discrepancy reports
        unique_discs: List[Discrepancy] = []
        seen_keys: Set[str] = set()
        for d in discrepancies:
            key = f"{d.discrepancy_type.value}:{sorted(d.involved_claim_ids)}:{sorted(d.involved_transaction_ids)}:{d.expected_value}:{d.observed_value}"
            if key not in seen_keys:
                seen_keys.add(key)
                unique_discs.append(d)

        # Count metrics
        crit_count = len([d for d in unique_discs if d.severity == DiscrepancySeverity.CRITICAL])
        err_count = len([d for d in unique_discs if d.severity == DiscrepancySeverity.ERROR])
        warn_count = len([d for d in unique_discs if d.severity == DiscrepancySeverity.WARNING])
        info_count = len([d for d in unique_discs if d.severity == DiscrepancySeverity.INFO])

        by_type_counts: Dict[str, int] = {}
        for d in unique_discs:
            by_type_counts[d.discrepancy_type.value] = by_type_counts.get(d.discrepancy_type.value, 0) + 1

        return ContradictionResult(
            discrepancies=unique_discs,
            total_contradictions=len(unique_discs),
            critical_count=crit_count,
            error_count=err_count,
            warning_count=warn_count,
            info_count=info_count,
            by_type=by_type_counts,
            metrics={
                "claims_evaluated": len(claims),
                "transactions_evaluated": len(transactions),
            },
        )
