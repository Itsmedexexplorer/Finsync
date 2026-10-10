"""Configuration for VERITY Contradiction Detection Subsystem."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContradictionConfig(BaseModel):
    """Configurable thresholds for contradiction detection."""
    max_acceptable_date_drift_days: int = Field(
        default=30,
        ge=0,
        description="Maximum acceptable settlement delay in days before flagging DATE_MISMATCH"
    )
    amount_tolerance_abs: float = Field(
        default=0.0,
        ge=0.0,
        description="Allowable currency difference in INR before flagging AMOUNT_MISMATCH"
    )
    flag_missing_evidence: bool = Field(
        default=True,
        description="Whether to flag assertions lacking supporting ledger evidence as MISSING_EVIDENCE"
    )
