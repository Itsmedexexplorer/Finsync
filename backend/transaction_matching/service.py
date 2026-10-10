"""Unified Transaction Matching Service for VERITY.

Orchestrates multi-signal matching between extracted Claims and verified ledger Transactions
leveraging Entity Resolution context.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.domain.claim import Claim
from backend.domain.reconciliation import MatchType
from backend.domain.transaction import Transaction
from backend.entity_resolution.service import EntityResolutionService
from backend.transaction_matching.base import BaseTransactionMatcher, MatchCandidate
from backend.transaction_matching.config import MatchConfig
from backend.transaction_matching.engine import TransactionMatcher
from backend.transaction_matching.result import (
    MatchRelationship,
    MatchRelationshipType,
    TransactionMatchingResult,
)


class TransactionMatchingService(BaseTransactionMatcher):
    """Central service managing financial record candidate pairing."""

    def __init__(
        self,
        config: Optional[MatchConfig] = None,
        entity_service: Optional[EntityResolutionService] = None,
    ) -> None:
        self.config = config or MatchConfig()
        self.matcher = TransactionMatcher(config=self.config)
        self.entity_service = entity_service

    def match_records(
        self,
        claims: List[Claim],
        transactions: List[Transaction],
        claim_entity_map: Optional[Dict[str, str]] = None,
    ) -> TransactionMatchingResult:
        """Run the full matching pipeline across claims and transactions."""
        entity_map = claim_entity_map or {}

        # If an EntityResolutionService is available and entity map not provided, resolve claims dynamically
        if not entity_map and self.entity_service:
            for c in claims:
                res = self.entity_service.resolve_claim(c)
                if res.selected_entity_id:
                    entity_map[c.id] = res.selected_entity_id

        return self.matcher.match(
            claims=claims,
            transactions=transactions,
            claim_entity_map=entity_map,
        )

    def match(
        self,
        claims: List[Claim],
        transactions: List[Transaction],
    ) -> List[MatchCandidate]:
        """Implements BaseTransactionMatcher protocol for backward compatibility."""
        result = self.match_records(claims, transactions)
        candidates: List[MatchCandidate] = []

        claim_lookup = {c.id: c for c in claims}
        txn_lookup = {t.id: t for t in transactions}

        for rel in result.relationships:
            matched_claims = [claim_lookup[cid] for cid in rel.source_claim_ids if cid in claim_lookup]
            matched_txns = [txn_lookup[tid] for tid in rel.target_transaction_ids if tid in txn_lookup]

            match_type_map = {
                MatchRelationshipType.ONE_TO_ONE: MatchType.EXACT_1_TO_1,
                MatchRelationshipType.MANY_TO_ONE: MatchType.MANY_TO_ONE,
                MatchRelationshipType.ONE_TO_MANY: MatchType.ONE_TO_MANY,
                MatchRelationshipType.PARTIAL: MatchType.PARTIAL_PAYMENT,
                MatchRelationshipType.CANDIDATE: MatchType.UNMATCHED,
            }
            cand_type = match_type_map.get(rel.relationship_type, MatchType.EXACT_1_TO_1)

            candidates.append(MatchCandidate(
                match_type=cand_type,
                claims=matched_claims,
                transactions=matched_txns,
                confidence=rel.score,
                reasoning=rel.explanation,
            ))

        return candidates
