"""Deduplication subsystem for cross-modal duplicate evidence and transaction detection."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Set, Tuple
from backend.domain.evidence import Evidence
from backend.domain.claim import Claim
from backend.domain.transaction import Transaction


class DuplicateGroup:
    """Represents a set of evidence or claims referring to the exact same underlying financial event."""
    def __init__(
        self,
        canonical_reference: str,
        primary_transaction: Optional[Transaction] = None,
        evidence_ids: Optional[List[str]] = None,
        claim_ids: Optional[List[str]] = None,
        confidence: float = 1.0,
    ) -> None:
        self.canonical_reference = canonical_reference
        self.primary_transaction = primary_transaction
        self.evidence_ids = evidence_ids or []
        self.claim_ids = claim_ids or []
        self.confidence = confidence


class BaseDeduplicator(ABC):
    """Abstract interface for cross-modal deduplication."""

    @abstractmethod
    def find_duplicates(
        self,
        evidence_items: List[Evidence],
        claims: List[Claim],
        transactions: List[Transaction],
    ) -> List[DuplicateGroup]:
        """Detect cross-modal duplicate assertions and return grouped duplicates."""
        pass
