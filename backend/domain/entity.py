"""Domain model for business and individual entities.

Supports entity resolution across multiple modalities, aliases, and Indian identifiers
(GSTIN, PAN, UPI VPA, Bank Accounts, Phone numbers).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field, field_validator


class EntityType(str, Enum):
    """Classification of the commercial entity."""
    INDIVIDUAL = "INDIVIDUAL"
    FREELANCER = "FREELANCER"
    SOLE_PROPRIETORSHIP = "SOLE_PROPRIETORSHIP"
    PARTNERSHIP = "PARTNERSHIP"
    PRIVATE_LIMITED = "PRIVATE_LIMITED"
    PUBLIC_LIMITED = "PUBLIC_LIMITED"
    LLP = "LLP"
    UNKNOWN = "UNKNOWN"


class BankAccountIdentifier(BaseModel):
    """Structured Indian bank account identifier."""
    account_number: str = Field(..., description="Bank account number or masked account number")
    ifsc_code: Optional[str] = Field(None, description="11-character Indian Financial System Code")
    bank_name: Optional[str] = Field(None, description="Name of the bank (e.g. HDFC, ICICI, SBI)")


class Entity(BaseModel):
    """Canonical representation of an Indian business entity or individual."""
    id: str = Field(..., description="Unique entity identifier, e.g. ENT-2026-001")
    canonical_name: str = Field(..., description="Standardized primary name of the entity")
    entity_type: EntityType = Field(default=EntityType.UNKNOWN, description="Entity type classification")
    
    # Official Indian Tax & Regulatory Identifiers
    gstin: Optional[str] = Field(
        default=None,
        description="15-character Goods and Services Tax Identification Number"
    )
    pan: Optional[str] = Field(
        default=None,
        description="10-character Permanent Account Number"
    )
    
    # Payment & Contact Handles
    upi_ids: List[str] = Field(
        default_factory=list,
        description="List of Virtual Payment Addresses (e.g. user@okhdfcbank)"
    )
    bank_accounts: List[BankAccountIdentifier] = Field(
        default_factory=list,
        description="Linked bank accounts"
    )
    phone_numbers: List[str] = Field(
        default_factory=list,
        description="Normalized E.164 phone numbers (e.g. +919876543210)"
    )
    emails: List[str] = Field(
        default_factory=list,
        description="Email addresses"
    )
    
    # Aliases & Discovered Names
    aliases: List[str] = Field(
        default_factory=list,
        description="Known variations, trading styles, or chat handles (e.g. 'M/s Ramesh Traders')"
    )
    
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when entity record was created"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary additional context"
    )

    def matches_alias_or_handle(self, query: str) -> bool:
        """Check if a string matches the canonical name, any alias, or handle (case-insensitive)."""
        normalized = query.strip().lower()
        if not normalized:
            return False
        
        # Check canonical name
        if normalized == self.canonical_name.strip().lower():
            return True
        
        # Check aliases
        for alias in self.aliases:
            if normalized == alias.strip().lower():
                return True
        
        # Check UPI IDs
        for upi in self.upi_ids:
            if normalized == upi.strip().lower():
                return True

        # Check phone numbers
        cleaned_digits = "".join(filter(str.isdigit, normalized))
        if cleaned_digits:
            for phone in self.phone_numbers:
                phone_digits = "".join(filter(str.isdigit, phone))
                if phone_digits and (cleaned_digits in phone_digits or phone_digits in cleaned_digits):
                    return True
                    
        return False
