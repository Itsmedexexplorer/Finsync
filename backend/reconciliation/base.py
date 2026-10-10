"""Base interface for Financial Reconciliation Subsystem."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from backend.domain.claim import Claim
from backend.domain.discrepancy import Discrepancy
from backend.domain.evidence import Evidence
from backend.domain.transaction import Transaction
from backend.reconciliation.result import ReconciliationResult


class BaseReconciler(ABC):
    """Abstract interface for financial reconciliation."""

    @abstractmethod
    def reconcile(
        self,
        claims: List[Claim],
        transactions: List[Transaction],
        evidence_items: Optional[List[Evidence]] = None,
        discrepancies: Optional[List[Discrepancy]] = None,
    ) -> List[ReconciliationResult]:
        """Synthesize verified financial conclusions."""
        pass
