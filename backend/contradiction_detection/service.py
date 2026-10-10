"""Unified Contradiction Detection Service for VERITY.

Orchestrates multi-signal contradiction rules across Claims, Transactions, Deduplication Groups,
and Match Relationships.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.contradiction_detection.base import BaseContradictionDetector
from backend.contradiction_detection.config import ContradictionConfig
from backend.contradiction_detection.detector import ContradictionDetector
from backend.contradiction_detection.result import ContradictionResult
from backend.deduplication.result import DeduplicationGroup
from backend.domain.claim import Claim
from backend.domain.discrepancy import Discrepancy
from backend.domain.transaction import Transaction
from backend.transaction_matching.result import MatchRelationship


class ContradictionDetectionService(BaseContradictionDetector):
    """Central service managing financial contradiction detection."""

    def __init__(self, config: Optional[ContradictionConfig] = None) -> None:
        self.config = config or ContradictionConfig()
        self.detector = ContradictionDetector(config=self.config)

    def detect_all(
        self,
        claims: List[Claim],
        transactions: List[Transaction],
        deduplication_groups: Optional[List[DeduplicationGroup]] = None,
        match_relationships: Optional[List[MatchRelationship]] = None,
        claim_entity_map: Optional[Dict[str, str]] = None,
    ) -> ContradictionResult:
        """Run full contradiction evaluation pipeline across all available context."""
        return self.detector.detect(
            claims=claims,
            transactions=transactions,
            deduplication_groups=deduplication_groups,
            match_relationships=match_relationships,
            claim_entity_map=claim_entity_map,
        )

    def detect_contradictions(
        self,
        claims: List[Claim],
        transactions: List[Transaction],
    ) -> List[Discrepancy]:
        """Implements BaseContradictionDetector protocol for backward compatibility."""
        result = self.detect_all(claims=claims, transactions=transactions)
        return result.discrepancies
