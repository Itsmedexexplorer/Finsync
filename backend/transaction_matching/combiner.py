"""Bounded Combination Matching for Many-to-One and One-to-Many Financial Relationships."""

from __future__ import annotations

import itertools
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.domain.claim import Claim
from backend.domain.transaction import Transaction
from backend.transaction_matching.config import MatchConfig
from backend.transaction_matching.result import (
    MatchRelationship,
    MatchRelationshipType,
    MatchStatus,
)
from backend.transaction_matching.signals import PairwiseSignalEvaluator


class CombinationMatcher:
    """Finds exact sum combinations for N:1 and 1:N match topologies with strict search bounds."""

    @classmethod
    def find_many_to_one_matches(
        cls,
        claims: List[Claim],
        transactions: List[Transaction],
        claim_entity_map: Optional[Dict[str, str]] = None,
        config: Optional[MatchConfig] = None,
    ) -> List[MatchRelationship]:
        """Finds N transactions that sum up to settle 1 invoice claim."""
        cfg = config or MatchConfig()
        entity_map = claim_entity_map or {}
        matches: List[MatchRelationship] = []
        matched_txn_ids: Set[str] = set()

        for claim in claims:
            if claim.claimed_amount is None or claim.claimed_amount <= 0:
                continue

            target_amount = float(claim.claimed_amount)
            claim_ent = entity_map.get(claim.id)

            # Candidate pool of transactions: compatible direction and not yet matched
            candidate_txns = [
                t for t in transactions
                if t.id not in matched_txn_ids
                and t.amount < target_amount  # Candidate components must be less than full target
            ]

            # If entity is known, prioritize/filter by entity
            if claim_ent:
                ent_txns = [t for t in candidate_txns if (t.origin_entity_id == claim_ent or t.destination_entity_id == claim_ent)]
                if ent_txns:
                    candidate_txns = ent_txns

            # Limit candidate search space to prevent combinatorial explosion
            bounded_pool = candidate_txns[:15]
            max_r = min(len(bounded_pool), cfg.max_combination_size)

            found_combo: Optional[Tuple[Transaction, ...]] = None

            for r in range(2, max_r + 1):
                for combo in itertools.combinations(bounded_pool, r):
                    combo_sum = sum(t.amount for t in combo)
                    if abs(combo_sum - target_amount) <= cfg.amount_tolerance_abs:
                        found_combo = combo
                        break
                if found_combo:
                    break

            if found_combo:
                txn_ids = [t.id for t in found_combo]
                matched_txn_ids.update(txn_ids)
                
                # Calculate aggregate scores across the combo
                scores = []
                for t in found_combo:
                    score, _, _, _ = PairwiseSignalEvaluator.evaluate_pair(claim, t, claim_ent, cfg)
                    scores.append(score)

                avg_score = sum(scores) / len(scores) if scores else 0.85
                amounts_str = " + ".join(f"₹{t.amount:,.2f}" for t in found_combo)
                rel_id = f"MAT-M2O-{uuid.uuid4().hex[:8]}"

                matches.append(MatchRelationship(
                    id=rel_id,
                    relationship_type=MatchRelationshipType.MANY_TO_ONE,
                    status=MatchStatus.MATCHED if avg_score >= cfg.min_score_matched else MatchStatus.PROBABLE,
                    source_claim_ids=[claim.id],
                    target_transaction_ids=txn_ids,
                    matched_amount=round(sum(t.amount for t in found_combo), 2),
                    target_amount=round(target_amount, 2),
                    score=round(avg_score, 2),
                    matched_signals=["SUM_AMOUNT_MATCH", f"{len(found_combo)}_ITEMS_SUM"],
                    conflicting_signals=[],
                    explanation=f"Many-to-One Match: {len(found_combo)} transactions ({amounts_str}) exactly sum to invoice total of ₹{target_amount:,.2f}.",
                    entity_id=claim_ent,
                ))

        return matches

    @classmethod
    def find_one_to_many_matches(
        cls,
        claims: List[Claim],
        transactions: List[Transaction],
        claim_entity_map: Optional[Dict[str, str]] = None,
        config: Optional[MatchConfig] = None,
    ) -> List[MatchRelationship]:
        """Finds 1 bulk transaction that settles N invoice claims."""
        cfg = config or MatchConfig()
        entity_map = claim_entity_map or {}
        matches: List[MatchRelationship] = []
        matched_claim_ids: Set[str] = set()

        for txn in transactions:
            target_amount = float(txn.amount)
            txn_ent = txn.origin_entity_id or txn.destination_entity_id

            # Candidate pool of claims: not yet matched and smaller than bulk transaction
            candidate_claims = [
                c for c in claims
                if c.id not in matched_claim_ids
                and c.claimed_amount is not None
                and c.claimed_amount < target_amount
            ]

            # If entity is known, prioritize/filter by entity
            if txn_ent:
                ent_claims = [c for c in candidate_claims if entity_map.get(c.id) == txn_ent]
                if ent_claims:
                    candidate_claims = ent_claims

            bounded_pool = candidate_claims[:15]
            max_r = min(len(bounded_pool), cfg.max_combination_size)

            found_combo: Optional[Tuple[Claim, ...]] = None

            for r in range(2, max_r + 1):
                for combo in itertools.combinations(bounded_pool, r):
                    combo_sum = sum(float(c.claimed_amount or 0) for c in combo)
                    if abs(combo_sum - target_amount) <= cfg.amount_tolerance_abs:
                        found_combo = combo
                        break
                if found_combo:
                    break

            if found_combo:
                claim_ids = [c.id for c in found_combo]
                matched_claim_ids.update(claim_ids)

                scores = []
                for c in found_combo:
                    score, _, _, _ = PairwiseSignalEvaluator.evaluate_pair(c, txn, entity_map.get(c.id), cfg)
                    scores.append(score)

                avg_score = sum(scores) / len(scores) if scores else 0.85
                amounts_str = " + ".join(f"₹{c.claimed_amount:,.2f}" for c in found_combo)
                rel_id = f"MAT-12M-{uuid.uuid4().hex[:8]}"

                matches.append(MatchRelationship(
                    id=rel_id,
                    relationship_type=MatchRelationshipType.ONE_TO_MANY,
                    status=MatchStatus.MATCHED if avg_score >= cfg.min_score_matched else MatchStatus.PROBABLE,
                    source_claim_ids=claim_ids,
                    target_transaction_ids=[txn.id],
                    matched_amount=round(target_amount, 2),
                    target_amount=round(sum(float(c.claimed_amount or 0) for c in found_combo), 2),
                    score=round(avg_score, 2),
                    matched_signals=["SUM_AMOUNT_MATCH", f"{len(found_combo)}_INVOICES_SUM"],
                    conflicting_signals=[],
                    explanation=f"One-to-Many Match: Bulk settlement of ₹{target_amount:,.2f} settles {len(found_combo)} invoices ({amounts_str}).",
                    entity_id=txn_ent,
                ))

        return matches
