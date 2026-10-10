"""Deterministic Transaction Matching Engine for VERITY.

Pairs financial claims and verified ledger transactions across 1:1, 1:N, N:1, Partial,
and Ambiguous topologies with strict False-Match prevention.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.domain.claim import Claim, ClaimType
from backend.domain.transaction import Transaction
from backend.transaction_matching.combiner import CombinationMatcher
from backend.transaction_matching.config import MatchConfig
from backend.transaction_matching.result import (
    MatchRelationship,
    MatchRelationshipType,
    MatchStatus,
    TransactionMatchingResult,
)
from backend.transaction_matching.signals import PairwiseSignalEvaluator


class TransactionMatcher:
    """Core deterministic transaction matching engine."""

    def __init__(self, config: Optional[MatchConfig] = None) -> None:
        self.config = config or MatchConfig()

    def match(
        self,
        claims: List[Claim],
        transactions: List[Transaction],
        claim_entity_map: Optional[Dict[str, str]] = None,
    ) -> TransactionMatchingResult:
        """Executes full matching pipeline across claims and transactions."""
        entity_map = claim_entity_map or {}
        relationships: List[MatchRelationship] = []
        
        matched_claim_ids: Set[str] = set()
        matched_txn_ids: Set[str] = set()

        # -------------------------------------------------------------
        # Phase 1: 1-to-1 Exact Reference & High-Confidence Matching
        # -------------------------------------------------------------
        # Evaluate pairwise scores for all candidate pairs
        pairwise_candidates: List[Tuple[float, Claim, Transaction, List[str], List[str], str]] = []

        for c in claims:
            c_ent = entity_map.get(c.id)
            for t in transactions:
                score, matched_sigs, conf_sigs, explanation = PairwiseSignalEvaluator.evaluate_pair(
                    claim=c,
                    transaction=t,
                    claim_entity_id=c_ent,
                    config=self.config,
                )
                # Only consider for 1:1 in Phase 1 if amounts match exactly, references match, or conflict
                if ("EXACT_AMOUNT_MATCH" in matched_sigs or "EXACT_REFERENCE" in matched_sigs or conf_sigs):
                    if score > 0.0 or conf_sigs:
                        pairwise_candidates.append((score, c, t, matched_sigs, conf_sigs, explanation))

        # Sort candidate pairs descending by score
        pairwise_candidates.sort(key=lambda x: x[0], reverse=True)

        # Check for conflicts and ambiguity per claim / transaction
        claim_candidates: Dict[str, List[Tuple[float, Transaction, List[str], List[str], str]]] = {}
        txn_candidates: Dict[str, List[Tuple[float, Claim, List[str], List[str], str]]] = {}

        for score, c, t, ms, cs, exp in pairwise_candidates:
            claim_candidates.setdefault(c.id, []).append((score, t, ms, cs, exp))
            txn_candidates.setdefault(t.id, []).append((score, c, ms, cs, exp))

        # Process 1:1 Pairs
        for score, c, t, ms, cs, exp in pairwise_candidates:
            if c.id in matched_claim_ids or t.id in matched_txn_ids:
                continue

            # Check if this pair has conflicting signals (e.g. conflicting entity)
            if cs:
                rel_id = f"MAT-CNF-{uuid.uuid4().hex[:8]}"
                relationships.append(MatchRelationship(
                    id=rel_id,
                    relationship_type=MatchRelationshipType.ONE_TO_ONE,
                    status=MatchStatus.CONFLICTING,
                    source_claim_ids=[c.id],
                    target_transaction_ids=[t.id],
                    matched_amount=t.amount,
                    target_amount=c.claimed_amount or t.amount,
                    score=score,
                    matched_signals=ms,
                    conflicting_signals=cs,
                    explanation=f"Conflicting match candidate: {exp}",
                    entity_id=entity_map.get(c.id),
                ))
                matched_claim_ids.add(c.id)
                matched_txn_ids.add(t.id)
                continue

            # Check Ambiguity: If this claim has multiple strong candidates with close scores
            competing_txns = claim_candidates.get(c.id, [])
            if len(competing_txns) > 1 and "EXACT_REFERENCE" not in ms:
                top_s = competing_txns[0][0]
                second_s = competing_txns[1][0]
                if abs(top_s - second_s) < self.config.ambiguity_delta_threshold:
                    # Ambiguous match! Do NOT arbitrarily pick one!
                    rel_id = f"MAT-AMB-{uuid.uuid4().hex[:8]}"
                    relationships.append(MatchRelationship(
                        id=rel_id,
                        relationship_type=MatchRelationshipType.ONE_TO_ONE,
                        status=MatchStatus.AMBIGUOUS,
                        source_claim_ids=[c.id],
                        target_transaction_ids=[t.id for _, t, _, _, _ in competing_txns[:2]],
                        matched_amount=t.amount,
                        target_amount=c.claimed_amount or t.amount,
                        score=top_s,
                        matched_signals=ms,
                        conflicting_signals=[],
                        explanation=f"Ambiguous Match: Claim {c.id} matches multiple candidate transactions with close scores ({top_s:.2f} vs {second_s:.2f}). Human review required.",
                        entity_id=entity_map.get(c.id),
                    ))
                    matched_claim_ids.add(c.id)
                    for _, comp_t, _, _, _ in competing_txns[:2]:
                        matched_txn_ids.add(comp_t.id)
                    continue

            # Check Ambiguity on Transaction side
            competing_claims = txn_candidates.get(t.id, [])
            if len(competing_claims) > 1 and "EXACT_REFERENCE" not in ms:
                top_s = competing_claims[0][0]
                second_s = competing_claims[1][0]
                if abs(top_s - second_s) < self.config.ambiguity_delta_threshold:
                    rel_id = f"MAT-AMB-{uuid.uuid4().hex[:8]}"
                    relationships.append(MatchRelationship(
                        id=rel_id,
                        relationship_type=MatchRelationshipType.ONE_TO_ONE,
                        status=MatchStatus.AMBIGUOUS,
                        source_claim_ids=[comp_c.id for _, comp_c, _, _, _ in competing_claims[:2]],
                        target_transaction_ids=[t.id],
                        matched_amount=t.amount,
                        target_amount=c.claimed_amount or t.amount,
                        score=top_s,
                        matched_signals=ms,
                        conflicting_signals=[],
                        explanation=f"Ambiguous Match: Transaction {t.id} matches multiple candidate claims ({top_s:.2f} vs {second_s:.2f}).",
                        entity_id=t.origin_entity_id or t.destination_entity_id,
                    ))
                    matched_txn_ids.add(t.id)
                    for _, comp_c, _, _, _ in competing_claims[:2]:
                        matched_claim_ids.add(comp_c.id)
                    continue

            # Check if this is an exact or high-confidence 1:1 match
            if "EXACT_AMOUNT_MATCH" in ms and score >= self.config.min_score_probable:
                rel_id = f"MAT-121-{uuid.uuid4().hex[:8]}"
                status = MatchStatus.MATCHED if score >= self.config.min_score_matched else MatchStatus.PROBABLE
                relationships.append(MatchRelationship(
                    id=rel_id,
                    relationship_type=MatchRelationshipType.ONE_TO_ONE,
                    status=status,
                    source_claim_ids=[c.id],
                    target_transaction_ids=[t.id],
                    matched_amount=t.amount,
                    target_amount=c.claimed_amount or t.amount,
                    score=score,
                    matched_signals=ms,
                    conflicting_signals=[],
                    explanation=f"1-to-1 Match: {exp}",
                    entity_id=entity_map.get(c.id) or t.origin_entity_id or t.destination_entity_id,
                ))
                matched_claim_ids.add(c.id)
                matched_txn_ids.add(t.id)

        # -------------------------------------------------------------
        # Phase 2: Combination Matching (Many-to-One and One-to-Many)
        # -------------------------------------------------------------
        remaining_claims = [c for c in claims if c.id not in matched_claim_ids]
        remaining_txns = [t for t in transactions if t.id not in matched_txn_ids]

        if remaining_claims and remaining_txns:
            # 1. Check Many-to-One
            m2o_matches = CombinationMatcher.find_many_to_one_matches(
                claims=remaining_claims,
                transactions=remaining_txns,
                claim_entity_map=entity_map,
                config=self.config,
            )
            for m in m2o_matches:
                relationships.append(m)
                matched_claim_ids.update(m.source_claim_ids)
                matched_txn_ids.update(m.target_transaction_ids)

            # Update remaining
            remaining_claims = [c for c in claims if c.id not in matched_claim_ids]
            remaining_txns = [t for t in transactions if t.id not in matched_txn_ids]

            # 2. Check One-to-Many
            o2m_matches = CombinationMatcher.find_one_to_many_matches(
                claims=remaining_claims,
                transactions=remaining_txns,
                claim_entity_map=entity_map,
                config=self.config,
            )
            for m in o2m_matches:
                relationships.append(m)
                matched_claim_ids.update(m.source_claim_ids)
                matched_txn_ids.update(m.target_transaction_ids)

        # -------------------------------------------------------------
        # Phase 3: Partial Payment Matching
        # -------------------------------------------------------------
        remaining_claims = [c for c in claims if c.id not in matched_claim_ids]
        remaining_txns = [t for t in transactions if t.id not in matched_txn_ids]

        for c in remaining_claims:
            c_ent = entity_map.get(c.id)
            for t in remaining_txns:
                if t.id in matched_txn_ids:
                    continue
                score, ms, cs, exp = PairwiseSignalEvaluator.evaluate_pair(c, t, c_ent, self.config)
                if "PARTIAL_AMOUNT_MATCH" in ms and score >= 0.50 and not cs:
                    # Established partial payment relationship
                    rel_id = f"MAT-PRT-{uuid.uuid4().hex[:8]}"
                    relationships.append(MatchRelationship(
                        id=rel_id,
                        relationship_type=MatchRelationshipType.PARTIAL,
                        status=MatchStatus.MATCHED if score >= self.config.min_score_matched else MatchStatus.PROBABLE,
                        source_claim_ids=[c.id],
                        target_transaction_ids=[t.id],
                        matched_amount=t.amount,
                        target_amount=c.claimed_amount or t.amount,
                        score=score,
                        matched_signals=ms,
                        conflicting_signals=[],
                        explanation=f"Partial Payment Relationship: {exp}",
                        entity_id=c_ent or t.origin_entity_id or t.destination_entity_id,
                    ))
                    matched_claim_ids.add(c.id)
                    matched_txn_ids.add(t.id)
                    break

        # -------------------------------------------------------------
        # Phase 4: Identify Unmatched Records
        # -------------------------------------------------------------
        unmatched_claims = [c.id for c in claims if c.id not in matched_claim_ids]
        unmatched_txns = [t.id for t in transactions if t.id not in matched_txn_ids]

        metrics = {
            "total_claims": len(claims),
            "total_transactions": len(transactions),
            "matched_relationships": len(relationships),
            "unmatched_claims_count": len(unmatched_claims),
            "unmatched_transactions_count": len(unmatched_txns),
            "topologies": {
                "ONE_TO_ONE": len([r for r in relationships if r.relationship_type == MatchRelationshipType.ONE_TO_ONE]),
                "MANY_TO_ONE": len([r for r in relationships if r.relationship_type == MatchRelationshipType.MANY_TO_ONE]),
                "ONE_TO_MANY": len([r for r in relationships if r.relationship_type == MatchRelationshipType.ONE_TO_MANY]),
                "PARTIAL": len([r for r in relationships if r.relationship_type == MatchRelationshipType.PARTIAL]),
            },
            "statuses": {
                "MATCHED": len([r for r in relationships if r.status == MatchStatus.MATCHED]),
                "PROBABLE": len([r for r in relationships if r.status == MatchStatus.PROBABLE]),
                "AMBIGUOUS": len([r for r in relationships if r.status == MatchStatus.AMBIGUOUS]),
                "CONFLICTING": len([r for r in relationships if r.status == MatchStatus.CONFLICTING]),
            }
        }

        return TransactionMatchingResult(
            relationships=relationships,
            unmatched_claim_ids=unmatched_claims,
            unmatched_transaction_ids=unmatched_txns,
            metrics=metrics,
        )
