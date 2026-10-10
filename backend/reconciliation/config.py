"""Configuration for VERITY Financial Reconciliation Subsystem."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReconciliationConfig(BaseModel):
    """Configurable parameters and safety thresholds for financial reconciliation."""
    date_tolerance_days: int = Field(
        default=7,
        ge=0,
        description="Allowable settlement window in days between obligation and ledger settlement"
    )
    minimum_confirmed_confidence: float = Field(
        default=0.90,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score required to declare CONFIRMED financial truth"
    )
    minimum_probable_confidence: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score required for probable reconciliation"
    )
    allow_partial_settlement: bool = Field(
        default=True,
        description="Whether to recognize valid partial payments and calculate outstanding balance"
    )
    require_entity_match_for_confirmation: bool = Field(
        default=True,
        description="Enforces that counterparty entity must be verified or compatible to confirm reconciliation"
    )
    amount_tolerance_abs: float = Field(
        default=0.0,
        ge=0.0,
        description="Allowable absolute currency discrepancy in INR before flagging mismatch"
    )
