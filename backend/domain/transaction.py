"""Domain model for verified financial transactions.

A Transaction represents an actual ledger event, typically verified via bank statements,
gateway webhooks/settlement reports, or recorded ledger entries.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class TransactionDirection(str, Enum):
    """Direction of funds relative to the user's account."""
    CREDIT = "CREDIT"   # Money received / inflow
    DEBIT = "DEBIT"     # Money sent / outflow


class PaymentMethod(str, Enum):
    """Standard payment rails in the Indian financial ecosystem."""
    UPI = "UPI"
    NEFT = "NEFT"
    RTGS = "RTGS"
    IMPS = "IMPS"
    CARD = "CARD"
    NETBANKING = "NETBANKING"
    CASH = "CASH"
    CHEQUE = "CHEQUE"
    GATEWAY = "GATEWAY"   # Razorpay, Cashfree, PayU, Stripe
    OTHER = "OTHER"


class Transaction(BaseModel):
    """Represents a verified movement of funds on an account or ledger."""
    id: str = Field(..., description="Unique transaction identifier, e.g. TXN-2026-001")
    amount: float = Field(..., description="Monetary value of the transaction (must be > 0)")
    currency: str = Field(default="INR", description="Three-letter ISO currency code")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the transaction settled"
    )
    direction: TransactionDirection = Field(
        ...,
        description="Funds direction (CREDIT for incoming, DEBIT for outgoing)"
    )
    payment_method: PaymentMethod = Field(
        default=PaymentMethod.UPI,
        description="Payment rail used"
    )
    bank_reference: Optional[str] = Field(
        default=None,
        description="Unique bank reference: UPI RRN (12 digits), NEFT/RTGS UTR, Cheque number"
    )
    narration: Optional[str] = Field(
        default=None,
        description="Raw statement narration string e.g. 'UPI/408219381920/PAYTO/RAMESH'"
    )
    origin_entity_id: Optional[str] = Field(
        default=None,
        description="Resolved or suggested sender Entity ID"
    )
    destination_entity_id: Optional[str] = Field(
        default=None,
        description="Resolved or suggested recipient Entity ID"
    )
    account_identifier: Optional[str] = Field(
        default=None,
        description="Account number or VPA on which this transaction occurred"
    )
    evidence_ids: List[str] = Field(
        default_factory=list,
        description="IDs of Evidence artifacts that substantiate this transaction"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional technical properties (e.g. running balance, MDR charges)"
    )

    @property
    def known_timestamp(self) -> Optional[datetime]:
        """The settlement time only if the source actually provided one.

        `timestamp` falls back to "now" when a feed has no date; date-based matching
        must ignore that placeholder or every undated transaction drifts out of range.
        """
        return self.timestamp if "timestamp" in self.model_fields_set else None

    @field_validator("amount")
    @classmethod
    def validate_amount_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Transaction amount must be strictly greater than 0")
        return round(v, 2)
