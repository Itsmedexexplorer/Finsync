"""Canonical Domain Models for VERITY — Financial Truth, Reconstructed.

Core Principle: Evidence != Claim != Conclusion.
"""

from backend.domain.evidence import (
    Evidence,
    EvidenceModality,
    EvidenceSourceType,
)
from backend.domain.claim import (
    Claim,
    ClaimType,
    ClaimStatus,
)
from backend.domain.entity import (
    Entity,
    EntityType,
    BankAccountIdentifier,
)
from backend.domain.transaction import (
    Transaction,
    TransactionDirection,
    PaymentMethod,
)
from backend.domain.discrepancy import (
    Discrepancy,
    DiscrepancyType,
    DiscrepancySeverity,
)
from backend.domain.provenance import (
    ProvenanceNode,
    ProvenanceNodeType,
    AuditTrail,
)
from backend.domain.reconciliation import (
    ReconciliationRecord,
    ReconciliationStatus,
    MatchType,
)

__all__ = [
    "Evidence",
    "EvidenceModality",
    "EvidenceSourceType",
    "Claim",
    "ClaimType",
    "ClaimStatus",
    "Entity",
    "EntityType",
    "BankAccountIdentifier",
    "Transaction",
    "TransactionDirection",
    "PaymentMethod",
    "Discrepancy",
    "DiscrepancyType",
    "DiscrepancySeverity",
    "ProvenanceNode",
    "ProvenanceNodeType",
    "AuditTrail",
    "ReconciliationRecord",
    "ReconciliationStatus",
    "MatchType",
]
