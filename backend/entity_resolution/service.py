"""Unified Entity Resolution Service for VERITY.

Orchestrates candidate generation, multi-signal scoring, ambiguity preservation,
and conflict detection for financial claims and queries.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from backend.domain.claim import Claim
from backend.domain.entity import Entity
from backend.entity_resolution.base import BaseEntityResolver
from backend.entity_resolution.matcher import EntityMatcher
from backend.entity_resolution.normalizer import EntityNormalizer
from backend.entity_resolution.registry import EntityRegistry
from backend.entity_resolution.result import (
    EntityCandidate,
    EntityResolutionResult,
    EntityResolutionStatus,
)


class EntityResolutionService(BaseEntityResolver):
    """Central service managing entity candidate retrieval, scoring, and resolution."""

    def __init__(self, registry: Optional[EntityRegistry] = None) -> None:
        self.registry = registry or EntityRegistry()

    def register_entity(self, entity: Entity) -> None:
        """Register a known business or individual entity."""
        self.registry.register_entity(entity)

    def resolve_entity(
        self,
        query_name: Optional[str] = None,
        query_handle: Optional[str] = None,
        query_tax_id: Optional[str] = None,
        query_phone: Optional[str] = None,
    ) -> Optional[tuple[Entity, float]]:
        """Implements BaseEntityResolver protocol for backward compatibility."""
        res = self.resolve_query(
            query_name=query_name,
            query_handle=query_handle,
            query_phone=query_phone,
            query_tax_id=query_tax_id,
        )
        if res.status in (EntityResolutionStatus.CONFIRMED, EntityResolutionStatus.PROBABLE) and res.selected_entity:
            return (res.selected_entity, res.score)
        return None

    def resolve_query(
        self,
        query_name: Optional[str] = None,
        query_handle: Optional[str] = None,
        query_phone: Optional[str] = None,
        query_tax_id: Optional[str] = None,
        claim_id: Optional[str] = None,
    ) -> EntityResolutionResult:
        """Resolve an arbitrary set of identity parameters against the entity registry."""
        # 1. Check if all parameters are empty
        if not any([query_name, query_handle, query_phone, query_tax_id]):
            return EntityResolutionResult(
                claim_id=claim_id,
                status=EntityResolutionStatus.UNRESOLVED,
                selected_entity_id=None,
                score=0.0,
                candidates=[],
                matched_signals=[],
                conflicting_signals=[],
                explanation="No identity parameters or counterparty hints provided.",
            )

        # 2. Retrieve candidate entities
        candidate_entities = self.registry.get_candidate_entities(
            query_name=query_name,
            query_handle=query_handle,
            query_phone=query_phone,
            query_tax_id=query_tax_id,
        )

        # If no candidates found from index, fallback to scanning all entities if query_name exists
        if not candidate_entities and query_name:
            candidate_entities = self.registry.list_all()

        # 3. Score each candidate
        scored_candidates: List[EntityCandidate] = []
        entity_map: Dict[str, Entity] = {}
        for ent in candidate_entities:
            entity_map[ent.id] = ent
            cand = EntityMatcher.evaluate_candidate(
                entity=ent,
                query_name=query_name,
                query_handle=query_handle,
                query_phone=query_phone,
                query_tax_id=query_tax_id,
            )
            if cand.score > 0.0 or cand.conflicting_signals:
                scored_candidates.append(cand)

        # 4. Resolve overall verdict
        return EntityMatcher.resolve_candidates(
            candidates=scored_candidates,
            claim_id=claim_id,
            entity_lookup=entity_map,
        )

    def resolve_claim(self, claim: Claim) -> EntityResolutionResult:
        """Extract identity hints from a Claim and resolve against the entity registry."""
        counterparty_hint = claim.counterparty_hint
        query_handle: Optional[str] = None
        query_phone: Optional[str] = None
        query_name: Optional[str] = None

        # Dissect counterparty hint if it contains UPI handle or phone
        if counterparty_hint:
            if "@" in counterparty_hint:
                query_handle = counterparty_hint.strip()
            elif re.search(r"^\+?\d{10,12}$", counterparty_hint.replace(" ", "").replace("-", "")):
                query_phone = counterparty_hint.strip()
            else:
                query_name = counterparty_hint.strip()

        # Check claim metadata for additional sender or identifier context
        meta_sender = claim.metadata.get("sender_metadata")
        if meta_sender and not query_name:
            query_name = meta_sender

        return self.resolve_query(
            query_name=query_name,
            query_handle=query_handle,
            query_phone=query_phone,
            claim_id=claim.id,
        )

    def resolve_claims_batch(self, claims: List[Claim]) -> List[EntityResolutionResult]:
        """Resolve a collection of claims in batch."""
        return [self.resolve_claim(c) for c in claims]
