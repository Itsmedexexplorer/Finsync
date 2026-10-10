"""Configuration parameters for VERITY Cross-Modal Deduplication Engine."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DeduplicationConfig(BaseModel):
    """Configurable parameters for cross-modal duplicate event detection."""
    date_tolerance_days: int = Field(
        default=3,
        ge=0,
        description="Maximum allowed difference in days between cross-modal assertions of the same event"
    )
    min_score_same_event: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Minimum score to classify evidence/claims as SAME_EVENT"
    )
    min_score_possible_dup: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
        description="Minimum score to classify evidence/claims as POSSIBLE_DUPLICATE"
    )
    amount_tolerance_abs: float = Field(
        default=0.0,
        ge=0.0,
        description="Allowable absolute currency discrepancy in INR"
    )
