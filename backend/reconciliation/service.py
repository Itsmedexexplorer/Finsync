"""Unified Financial Reconciliation Service for VERITY.

Orchestrates multi-stage financial truth reconstruction across Evidence, Claims, Entities,
Matches, Deduplication Groups, and Discrepancies.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.deduplication.result import DeduplicationGroup
from backend.domain.claim import Claim
from backend.domain.discrepancy import Discrepancy
from backend.domain.entity import Entity
from backend.domain.evidence import Evidence
from backend.domain.reconciliation import ReconciliationRecord
from backend.domain.transaction import Transaction
from backend.provenance.tracker import ProvenanceTracker
from backend.reconciliation.base import BaseReconciler
from backend.reconciliation.config import ReconciliationConfig
from backend.reconciliation.engine import ReconciliationEngine
from backend.reconciliation.result import BatchReconciliationResult, ReconciliationResult
from backend.transaction_matching.result import MatchRelationship


class ReconciliationService(BaseReconciler):
    """Central service synthesizing final verified financial conclusions."""

    def __init__(
        self,
        config: Optional[ReconciliationConfig] = None,
        provenance_tracker: Optional[ProvenanceTracker] = None,
    ) -> None:
        self.config = config or ReconciliationConfig()
        self.tracker = provenance_tracker or ProvenanceTracker()
        self.engine = ReconciliationEngine(config=self.config, provenance_tracker=self.tracker)

    def reconcile_all(
        self,
        claims: List[Claim],
        transactions: List[Transaction],
        evidence_items: Optional[List[Evidence]] = None,
        deduplication_groups: Optional[List[DeduplicationGroup]] = None,
        match_relationships: Optional[List[MatchRelationship]] = None,
        discrepancies: Optional[List[Discrepancy]] = None,
        claim_entity_map: Optional[Dict[str, str]] = None,
    ) -> BatchReconciliationResult:
        """Runs the complete reconciliation pipeline across all provided multimodal context."""
        return self.engine.reconcile(
            claims=claims,
            transactions=transactions,
            evidence_items=evidence_items,
            deduplication_groups=deduplication_groups,
            match_relationships=match_relationships,
            discrepancies=discrepancies,
            claim_entity_map=claim_entity_map,
        )

    def reconcile_events(
        self,
        claims: List[Claim],
        transactions: List[Transaction],
        evidence_items: Optional[List[Evidence]] = None,
        deduplication_groups: Optional[List[DeduplicationGroup]] = None,
        match_relationships: Optional[List[MatchRelationship]] = None,
        discrepancies: Optional[List[Discrepancy]] = None,
        claim_entity_map: Optional[Dict[str, str]] = None,
    ) -> List[ReconciliationResult]:
        """Returns list of ReconciliationResult objects across all events."""
        batch = self.reconcile_all(
            claims=claims,
            transactions=transactions,
            evidence_items=evidence_items,
            deduplication_groups=deduplication_groups,
            match_relationships=match_relationships,
            discrepancies=discrepancies,
            claim_entity_map=claim_entity_map,
        )
        return batch.results

    def reconcile_event(
        self,
        claims: List[Claim],
        transactions: List[Transaction],
        evidence_items: Optional[List[Evidence]] = None,
        match_relationship: Optional[MatchRelationship] = None,
        discrepancies: Optional[List[Discrepancy]] = None,
        claim_entity_map: Optional[Dict[str, str]] = None,
    ) -> ReconciliationResult:
        """Reconciles a single financial event context."""
        match_rels = [match_relationship] if match_relationship else None
        results = self.reconcile_events(
            claims=claims,
            transactions=transactions,
            evidence_items=evidence_items,
            match_relationships=match_rels,
            discrepancies=discrepancies,
            claim_entity_map=claim_entity_map,
        )
        return results[0] if results else None  # type: ignore[return-value]

    def reconcile(
        self,
        claims: List[Claim],
        transactions: List[Transaction],
        evidence_items: Optional[List[Evidence]] = None,
        discrepancies: Optional[List[Discrepancy]] = None,
    ) -> List[ReconciliationResult]:
        """Implements BaseReconciler protocol."""
        return self.reconcile_events(
            claims=claims,
            transactions=transactions,
            evidence_items=evidence_items,
            discrepancies=discrepancies,
        )

    def reconcile_case(
        self,
        reconciliation_id: str,
        evidence_items: List[Evidence],
        claims: List[Claim],
        transactions: List[Transaction],
        counterparty: Optional[Entity] = None,
    ) -> ReconciliationRecord:
        """Backward compatibility with Day 1 case evaluation."""
        return self.engine.reconcile_case(
            reconciliation_id=reconciliation_id,
            evidence_items=evidence_items,
            claims=claims,
            transactions=transactions,
            counterparty=counterparty,
        )
