"""Contradiction Detection subsystem for identifying conflicting financial claims and ledger realities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
from backend.domain.claim import Claim
from backend.domain.transaction import Transaction
from backend.domain.discrepancy import Discrepancy, DiscrepancySeverity, DiscrepancyType


class BaseContradictionDetector(ABC):
    """Abstract interface for contradiction detection."""

    @abstractmethod
    def detect_contradictions(
        self,
        claims: List[Claim],
        transactions: List[Transaction],
    ) -> List[Discrepancy]:
        """Compare claims against other claims and verified transactions to discover contradictions."""
        pass
