"""Result models for VERITY Financial Reconciliation Subsystem."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.domain.discrepancy import Discrepancy
from backend.domain.reconciliation import MatchType, ReconciliationRecord, ReconciliationStatus


class ReconciliationResult(BaseModel):
    """The synthesized, explainable financial reconciliation result for an event or obligation."""
    reconciliation_id: str = Field(..., description="Unique reconciliation ID, e.g. REC-2026-001")
    status: ReconciliationStatus = Field(..., description="Final financial conclusion status")
    event_id: Optional[str] = Field(default=None, description="Associated deduplicated event group ID")
    entity_id: Optional[str] = Field(default=None, description="Resolved counterparty entity ID")

    # Member links
    claim_ids: List[str] = Field(default_factory=list, description="All Claim IDs evaluated")
    transaction_ids: List[str] = Field(default_factory=list, description="All Transaction IDs verified")
    evidence_ids: List[str] = Field(default_factory=list, description="All root Evidence IDs involved")

    # Financial accounting values
    expected_amount: Optional[float] = Field(default=None, description="Total expected or invoiced amount (INR)")
    matched_amount: float = Field(default=0.0, description="Total substantiated on ledger (INR)")
    outstanding_amount: float = Field(default=0.0, description="Unsettled balance remaining (INR)")
    currency: str = Field(default="INR", description="Three-letter ISO currency code")

    # Confidence and signals
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)")
    supporting_signals: List[str] = Field(default_factory=list, description="List of corroborated positive signals")
    contradicting_signals: List[str] = Field(default_factory=list, description="List of unresolved contradiction signals")

    # Pipeline references
    discrepancy_ids: List[str] = Field(default_factory=list, description="Linked Discrepancy IDs")
    match_relationship_ids: List[str] = Field(default_factory=list, description="Linked Day 5 Match IDs")
    deduplication_group_ids: List[str] = Field(default_factory=list, description="Linked Day 6 Group IDs")

    # Justification
    explanation: str = Field(..., description="Clear human-readable justification of the financial conclusion")
    reason_codes: List[str] = Field(default_factory=list, description="Deterministic rule codes applied")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Audit trail and lineage references")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic properties")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_domain_record(self, discrepancies: Optional[List[Discrepancy]] = None) -> ReconciliationRecord:
        """Converts to canonical ReconciliationRecord domain model."""
        match_type_val = MatchType.EXACT_1_TO_1
        if self.status in (ReconciliationStatus.PARTIAL, ReconciliationStatus.PARTIALLY_SETTLED):
            match_type_val = MatchType.PARTIAL_PAYMENT
        elif self.status == ReconciliationStatus.CONTRADICTED:
            match_type_val = MatchType.CONTRADICTED_ASSERTION
        elif self.status == ReconciliationStatus.UNMATCHED:
            match_type_val = MatchType.UNMATCHED
        elif len(self.transaction_ids) > 1:
            match_type_val = MatchType.MANY_TO_ONE
        elif len(self.claim_ids) > 1:
            match_type_val = MatchType.ONE_TO_MANY

        return ReconciliationRecord(
            id=self.reconciliation_id,
            status=self.status,
            match_type=match_type_val,
            expected_amount=self.expected_amount,
            reconciled_amount=self.matched_amount,
            outstanding_amount=self.outstanding_amount,
            currency=self.currency,
            entity_id=self.entity_id,
            evidence_ids=self.evidence_ids,
            claim_ids=self.claim_ids,
            transaction_ids=self.transaction_ids,
            discrepancies=discrepancies or [],
            confidence_score=self.confidence_score,
            explanation_summary=self.explanation,
            created_at=self.created_at,
            metadata=self.metadata,
        )


class BatchReconciliationResult(BaseModel):
    """Aggregate result holding multiple reconciliation conclusions."""
    results: List[ReconciliationResult] = Field(default_factory=list)
    total_reconciled_amount: float = Field(default=0.0)
    total_outstanding_amount: float = Field(default=0.0)
    status_counts: Dict[str, int] = Field(default_factory=dict)
    summary_metrics: Dict[str, Any] = Field(default_factory=dict)
