"""Domain model for raw financial evidence.

Principle: Evidence is the raw, unprocessed artifact captured from the real world.
Evidence != Claim != Conclusion.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class EvidenceModality(str, Enum):
    """The sensory / medium type of the captured evidence."""
    BANK_STATEMENT = "BANK_STATEMENT"
    INVOICE = "INVOICE"
    RECEIPT = "RECEIPT"
    PAYMENT_SCREENSHOT = "PAYMENT_SCREENSHOT"
    MESSAGING_CHAT = "MESSAGING_CHAT"
    CASH_VOUCHER = "CASH_VOUCHER"
    PAYMENT_GATEWAY_EXPORT = "PAYMENT_GATEWAY_EXPORT"
    OTHER = "OTHER"


class EvidenceSourceType(str, Enum):
    """The origin mechanism or system that generated the evidence."""
    BANK_CSV = "BANK_CSV"
    BANK_PDF = "BANK_PDF"
    WHATSAPP_EXPORT = "WHATSAPP_EXPORT"
    SMS_TEXT = "SMS_TEXT"
    ZOHO_INVOICE = "ZOHO_INVOICE"
    TALLY_EXPORT = "TALLY_EXPORT"
    RAZORPAY_FEED = "RAZORPAY_FEED"
    MANUAL_UPLOAD = "MANUAL_UPLOAD"
    PAPER_SCAN = "PAPER_SCAN"
    SYSTEM_SYNTHETIC = "SYSTEM_SYNTHETIC"


class Evidence(BaseModel):
    """Represents a piece of raw financial evidence observed in the wild.
    
    Evidence stores raw content without interpreting claims or drawing conclusions.
    """
    id: str = Field(..., description="Unique evidence identifier, e.g. EVID-2026-001")
    modality: EvidenceModality = Field(..., description="The modality of the evidence")
    source_type: EvidenceSourceType = Field(..., description="The origin source channel")
    source_name: str = Field(..., description="Human-readable source name, e.g. 'HDFC_Bank_Stmt_Aug2026.csv'")
    raw_payload: str = Field(..., description="The raw unparsed payload, message string, or text content")
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when this evidence was ingested"
    )
    content_hash: str = Field(
        default="",
        description="Cryptographic SHA-256 hash of the raw payload for tamper-evidence"
    )
    language_hint: Optional[str] = Field(
        default="en",
        description="Language code or hint e.g. 'en', 'hi', 'hinglish', 'ta'"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible key-value metadata (e.g. sender phone, file size, mime type)"
    )

    def model_post_init(self, __context: Any) -> None:
        """Compute SHA-256 content hash automatically if not explicitly provided."""
        if not self.content_hash and self.raw_payload:
            computed_hash = hashlib.sha256(self.raw_payload.encode("utf-8")).hexdigest()
            # Pydantic v2 allows setting attribute in model_post_init
            object.__setattr__(self, "content_hash", computed_hash)
