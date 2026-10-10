"""Unified Cross-Modal Deduplication Service for VERITY.

Orchestrates multi-signal evidence clustering, content deduplication, and event grouping.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.deduplication.base import BaseDeduplicator, DuplicateGroup
from backend.deduplication.config import DeduplicationConfig
from backend.deduplication.engine import DeduplicationEngine
from backend.deduplication.result import (
    DeduplicationGroup,
    DeduplicationResult,
    DeduplicationStatus,
)
from backend.domain.claim import Claim
from backend.domain.evidence import Evidence
from backend.domain.transaction import Transaction
from backend.transaction_matching.result import MatchRelationship


class DeduplicationService(BaseDeduplicator):
    """Central service managing cross-modal evidence deduplication and event grouping."""

    def __init__(self, config: Optional[DeduplicationConfig] = None) -> None:
        self.config = config or DeduplicationConfig()
        self.engine = DeduplicationEngine(config=self.config)

    def deduplicate_records(
        self,
        evidence_items: List[Evidence],
        claims: Optional[List[Claim]] = None,
        transactions: Optional[List[Transaction]] = None,
        claim_entity_map: Optional[Dict[str, str]] = None,
        match_relationships: Optional[List[MatchRelationship]] = None,
    ) -> DeduplicationResult:
        """Run the full deduplication pipeline across multimodal artifacts."""
        return self.engine.deduplicate(
            evidence_items=evidence_items,
            claims=claims,
            transactions=transactions,
            claim_entity_map=claim_entity_map,
            match_relationships=match_relationships,
        )

    def find_duplicates(
        self,
        evidence_items: List[Evidence],
        claims: List[Claim],
        transactions: List[Transaction],
    ) -> List[DuplicateGroup]:
        """Implements BaseDeduplicator protocol for backward compatibility."""
        result = self.deduplicate_records(
            evidence_items=evidence_items,
            claims=claims,
            transactions=transactions,
        )
        groups: List[DuplicateGroup] = []

        txn_lookup = {t.id: t for t in transactions}

        for g in result.groups:
            if g.status in (DeduplicationStatus.SAME_EVENT, DeduplicationStatus.POSSIBLE_DUPLICATE, DeduplicationStatus.DUPLICATE_EVIDENCE_CONTENT):
                primary_txn = txn_lookup.get(g.candidate_transaction_ids[0]) if g.candidate_transaction_ids else None
                ref = g.canonical_event_candidate.get("reference") or g.canonical_event_candidate.get("reference_key") or g.group_id

                groups.append(DuplicateGroup(
                    canonical_reference=ref,
                    primary_transaction=primary_txn,
                    evidence_ids=g.member_evidence_ids,
                    claim_ids=g.member_claim_ids,
                    confidence=g.score,
                ))

        return groups
