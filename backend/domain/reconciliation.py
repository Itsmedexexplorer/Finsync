"""Domain model for reconciliation conclusions and results.

Principle: Reconciliation is the Conclusion synthesized by VERITY after analyzing
Evidence, evaluating Claims, resolving Entities, and matching Transactions.
Evidence != Claim != Conclusion.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.domain.discrepancy import Discrepancy


class ReconciliationStatus(str, Enum):
    """The synthesized financial conclusion status."""
    CONFIRMED = "CONFIRMED"         # 100% corroborated by ledger transactions and evidence
    PARTIAL = "PARTIAL"             # Valid transaction received, but covers only part of the invoice/claim
    PARTIALLY_SETTLED = "PARTIALLY_SETTLED" # Alias for partial settlement
    DUPLICATE = "DUPLICATE"         # Redundant proof detected across multiple evidence modalities
    CONTRADICTED = "CONTRADICTED"   # Conflicting assertions (e.g. claimed paid vs failed/lesser amount)
    UNVERIFIABLE = "UNVERIFIABLE"   # Assertion lacks ledger proof, missing counterparty, or unsupported cash claim
    AMBIGUOUS = "AMBIGUOUS"         # Multiple valid candidate interpretations requiring user review
    UNMATCHED = "UNMATCHED"         # Unmatched standalone transaction or obligation


class MatchType(str, Enum):
    """The topological match pattern identified by the engine."""
    EXACT_1_TO_1 = "EXACT_1_TO_1"                       # 1 Invoice <-> 1 Transaction
    ONE_TO_MANY = "ONE_TO_MANY"                         # 1 Transaction settles N Invoices
    MANY_TO_ONE = "MANY_TO_ONE"                         # N Transactions settle 1 Invoice
    PARTIAL_PAYMENT = "PARTIAL_PAYMENT"                 # Transaction < Invoice amount
    CROSS_MODAL_DUPLICATE = "CROSS_MODAL_DUPLICATE"     # Screenshot + Bank CSV for same transaction
    CONTRADICTED_ASSERTION = "CONTRADICTED_ASSERTION"   # Claim contradicted by bank settlement
    UNMATCHED = "UNMATCHED"                             # Evidence / transaction with no pair


class ReconciliationRecord(BaseModel):
    """Represents a verified financial conclusion reached for a set of evidence, claims, and transactions."""
    id: str = Field(..., description="Unique reconciliation conclusion ID, e.g. REC-2026-001")
    status: ReconciliationStatus = Field(..., description="Synthesized financial status")
    match_type: MatchType = Field(default=MatchType.EXACT_1_TO_1, description="Topological match pattern")
    
    # Financial Accounting Amounts
    expected_amount: Optional[float] = Field(
        default=None,
        description="The full expected or invoiced amount (INR)"
    )
    reconciled_amount: float = Field(
        default=0.0,
        description="The verified monetary amount substantiated on ledger (INR)"
    )
    outstanding_amount: float = Field(
        default=0.0,
        description="Remaining balance outstanding (INR), if any"
    )
    currency: str = Field(default="INR", description="Three-letter ISO currency code")
    
    # Linked Domain Artifacts
    entity_id: Optional[str] = Field(
        default=None,
        description="Resolved counterparty entity ID"
    )
    evidence_ids: List[str] = Field(
        default_factory=list,
        description="All Evidence artifact IDs involved in this conclusion"
    )
    claim_ids: List[str] = Field(
        default_factory=list,
        description="All Claim IDs evaluated"
    )
    transaction_ids: List[str] = Field(
        default_factory=list,
        description="All Transaction IDs verified and attached"
    )
    
    # Discrepancies & Audit Diagnostics
    discrepancies: List[Discrepancy] = Field(
        default_factory=list,
        description="List of all detected anomalies or exceptions"
    )
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for this reconciliation conclusion (0.0 to 1.0)"
    )
    explanation_summary: str = Field(
        ...,
        description="Clear human-readable justification of the financial conclusion"
    )
    
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when reconciliation was synthesized"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary additional diagnostic metadata"
    )
