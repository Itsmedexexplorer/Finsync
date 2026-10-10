"""Domain model for discrepancies, anomalies, and exceptions in financial reconciliation.

Captures precisely what went wrong, what conflicted, or why a conclusion is partial/unverifiable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DiscrepancyType(str, Enum):
    """Categorization of the reconciliation anomaly or contradiction."""
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    DATE_OUT_OF_WINDOW = "DATE_OUT_OF_WINDOW"
    DATE_MISMATCH = "DATE_MISMATCH"
    CONTRADICTORY_CLAIM = "CONTRADICTORY_CLAIM"
    CONFLICTING_CLAIMS = "CONFLICTING_CLAIMS"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    DUPLICATE_EVIDENCE = "DUPLICATE_EVIDENCE"
    DUPLICATE_REFERENCE_CONFLICT = "DUPLICATE_REFERENCE_CONFLICT"
    UNRESOLVED_ENTITY = "UNRESOLVED_ENTITY"
    ENTITY_MISMATCH = "ENTITY_MISMATCH"
    INVALID_REFERENCE_ID = "INVALID_REFERENCE_ID"
    REFERENCE_MISMATCH = "REFERENCE_MISMATCH"
    DIRECTION_MISMATCH = "DIRECTION_MISMATCH"
    PAYMENT_RAIL_MISMATCH = "PAYMENT_RAIL_MISMATCH"
    UNVERIFIABLE_CASH_CLAIM = "UNVERIFIABLE_CASH_CLAIM"
    PARTIAL_SETTLEMENT = "PARTIAL_SETTLEMENT"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
    BOUNCED_OR_FAILED_PAYMENT = "BOUNCED_OR_FAILED_PAYMENT"


class DiscrepancySeverity(str, Enum):
    """Severity of the discrepancy for the finance controller."""
    INFO = "INFO"           # Informational (e.g. cross-modal duplicate detected and merged)
    WARNING = "WARNING"     # Partial payment or non-standard reference ID
    ERROR = "ERROR"         # Amount mismatch or missing settlement proof
    CRITICAL = "CRITICAL"   # Direct contradiction or potential fraud


class Discrepancy(BaseModel):
    """Structured representation of a reconciliation discrepancy or exception."""
    id: str = Field(..., description="Unique discrepancy ID, e.g. DISC-2026-001")
    discrepancy_type: DiscrepancyType = Field(..., description="Categorization of the anomaly")
    severity: DiscrepancySeverity = Field(
        default=DiscrepancySeverity.WARNING,
        description="Severity level"
    )
    message: str = Field(..., description="Human-readable explanation of the discrepancy")
    
    # Associated Artifacts
    involved_evidence_ids: List[str] = Field(default_factory=list)
    involved_claim_ids: List[str] = Field(default_factory=list)
    involved_transaction_ids: List[str] = Field(default_factory=list)
    
    # Quantitative & Contextual Values
    expected_value: Optional[str] = Field(
        default=None,
        description="Expected value (e.g. '50000.00' or 'UTR-123456789012')"
    )
    observed_value: Optional[str] = Field(
        default=None,
        description="Observed value (e.g. '35000.00' or 'UTR-123456789019')"
    )
    
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when discrepancy was logged"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional technical properties"
    )
