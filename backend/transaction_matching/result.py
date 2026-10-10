"""Result and relationship models for VERITY Transaction Matching Subsystem.

Represents candidate matching relationships without making final financial reconciliation conclusions.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MatchRelationshipType(str, Enum):
    """Topological relationship structure between financial records."""
    ONE_TO_ONE = "ONE_TO_ONE"         # 1 Invoice / Claim <-> 1 Payment / Transaction
    MANY_TO_ONE = "MANY_TO_ONE"       # Multiple Payments / Transactions settle 1 Invoice
    ONE_TO_MANY = "ONE_TO_MANY"       # 1 Bulk Payment settles multiple Invoices
    PARTIAL = "PARTIAL"               # Partial payment relationship (Payment < Invoiced)
    CANDIDATE = "CANDIDATE"           # General candidate relationship


class MatchStatus(str, Enum):
    """Confidence status of the matching relationship."""
    MATCHED = "MATCHED"               # High-confidence relationship with strong corroborating signals
    PROBABLE = "PROBABLE"             # Probable relationship based on partial or medium signals
    AMBIGUOUS = "AMBIGUOUS"           # Multiple competing candidate pairings with similar confidence
    CONFLICTING = "CONFLICTING"       # Conflicting signals detected (e.g. matching amount but conflicting entity)
    UNMATCHED = "UNMATCHED"           # Financial record with no plausible matching relationship


class MatchRelationship(BaseModel):
    """Explicit candidate matching relationship between claims and transactions."""
    id: str = Field(..., description="Unique match relationship identifier, e.g. MAT-2026-001")
    relationship_type: MatchRelationshipType = Field(..., description="Topological relationship type")
    status: MatchStatus = Field(..., description="Relationship confidence status")
    
    # Linked source and target record IDs
    source_claim_ids: List[str] = Field(
        default_factory=list,
        description="IDs of source Claims (e.g. Invoices, payment promises)"
    )
    target_transaction_ids: List[str] = Field(
        default_factory=list,
        description="IDs of target Transactions or payment claims"
    )
    
    # Financial amounts involved
    matched_amount: float = Field(..., description="Settlement / payment amount in this relationship (INR)")
    target_amount: float = Field(..., description="Invoiced / expected amount in this relationship (INR)")
    
    # Scoring & Explainability
    score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Relationship match score (0.0 to 1.0)"
    )
    matched_signals: List[str] = Field(
        default_factory=list,
        description="List of positive matching signals"
    )
    conflicting_signals: List[str] = Field(
        default_factory=list,
        description="List of contradictory signals"
    )
    explanation: str = Field(..., description="Transparent human-readable justification for this relationship")
    
    entity_id: Optional[str] = Field(
        default=None,
        description="Associated counterparty Entity ID if resolved"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional technical diagnostics"
    )


class TransactionMatchingResult(BaseModel):
    """Aggregate output containing all resolved match relationships and unmatched records."""
    relationships: List[MatchRelationship] = Field(
        default_factory=list,
        description="List of established candidate match relationships"
    )
    unmatched_claim_ids: List[str] = Field(
        default_factory=list,
        description="IDs of Claims that could not be matched"
    )
    unmatched_transaction_ids: List[str] = Field(
        default_factory=list,
        description="IDs of Transactions that could not be matched"
    )
    metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Diagnostics (counts of 1:1, 1:N, N:1, ambiguous, conflicting, runtime)"
    )
