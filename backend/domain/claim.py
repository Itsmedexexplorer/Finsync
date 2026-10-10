"""Domain model for financial claims extracted from evidence.

Principle: A Claim is an assertion made by or within an Evidence artifact.
A claim may be true, false, incomplete, or contradicted by other evidence.
Evidence != Claim != Conclusion.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator


class ClaimType(str, Enum):
    """The type of assertion being made."""
    PAYMENT_SENT = "PAYMENT_SENT"                   # e.g., "I sent 25k on GPay"
    PAYMENT_RECEIVED = "PAYMENT_RECEIVED"           # e.g., "Received advance 10k"
    INVOICE_ISSUED = "INVOICE_ISSUED"               # e.g., "Invoice #INV-102 for Rs. 50,000"
    CASH_PAYMENT_PROMISE = "CASH_PAYMENT_PROMISE"   # e.g., "Paid cash in hand"
    REFUND_REQUESTED = "REFUND_REQUESTED"           # e.g., "Returned item, refund due"
    DISCOUNT_APPLIED = "DISCOUNT_APPLIED"           # e.g., "5% early settlement discount"
    EXPENSE_INCURRED = "EXPENSE_INCURRED"           # e.g., "Cab bill for client visit"


class ClaimStatus(str, Enum):
    """The validation status of this specific claim during reconciliation."""
    ASSERTED = "ASSERTED"       # Extracted claim, unverified
    VALIDATED = "VALIDATED"     # Substantiated by ledger / bank transaction
    REFUTED = "REFUTED"         # Contradicted by reliable ground evidence
    AMBIGUOUS = "AMBIGUOUS"     # Multiple conflicting interpretations possible
    SUPERSEDED = "SUPERSEDED"   # Replaced by updated claim or revised invoice


class Claim(BaseModel):
    """Represents a specific financial assertion extracted from an Evidence item."""
    id: str = Field(..., description="Unique claim identifier, e.g. CLM-2026-001")
    evidence_id: str = Field(..., description="ID of the Evidence from which this claim was extracted")
    claim_type: ClaimType = Field(..., description="Type of financial assertion")
    claimed_amount: Optional[float] = Field(default=None, description="The numeric amount asserted (must be >= 0 if present)")
    currency: str = Field(default="INR", description="Three-letter ISO currency code, default INR")
    claimed_date: Optional[str] = Field(
        default=None,
        description="Date asserted in ISO format (YYYY-MM-DD) or natural text hint"
    )
    counterparty_hint: Optional[str] = Field(
        default=None,
        description="Asserted name, phone, or handle of the other party"
    )
    reference_id_hint: Optional[str] = Field(
        default=None,
        description="Asserted UTR, RRN, invoice number, or cheque reference"
    )
    payment_method_hint: Optional[str] = Field(
        default=None,
        description="Asserted payment rail (e.g. 'UPI', 'NEFT', 'CASH', 'GPAY')"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score of the claim extraction (0.0 to 1.0)"
    )
    raw_text_snippet: Optional[str] = Field(
        default=None,
        description="The verbatim text or segment from which this claim was drawn"
    )
    status: ClaimStatus = Field(
        default=ClaimStatus.ASSERTED,
        description="Current verification status of this claim"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when claim was created"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary additional extraction metadata"
    )

    @field_validator("claimed_amount")
    @classmethod
    def validate_amount_non_negative(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if v < 0:
                raise ValueError("Claimed amount cannot be negative")
            return round(v, 2)
        return None
