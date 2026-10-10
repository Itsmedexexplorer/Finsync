"""Transaction Matching subsystem for pairing Claims, Invoices, and Verified Transactions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from backend.domain.claim import Claim
from backend.domain.transaction import Transaction
from backend.domain.reconciliation import MatchType, ReconciliationRecord


class MatchCandidate:
    """A proposed grouping of claims and transactions."""
    def __init__(
        self,
        match_type: MatchType,
        claims: List[Claim],
        transactions: List[Transaction],
        confidence: float,
        reasoning: str,
    ) -> None:
        self.match_type = match_type
        self.claims = claims
        self.transactions = transactions
        self.confidence = confidence
        self.reasoning = reasoning


class BaseTransactionMatcher(ABC):
    """Abstract interface for matching transactions against claims."""

    @abstractmethod
    def match(
        self,
        claims: List[Claim],
        transactions: List[Transaction],
    ) -> List[MatchCandidate]:
        """Generate match candidates from given claims and verified ledger transactions."""
        pass
