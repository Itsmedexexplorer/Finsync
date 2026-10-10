"""Configuration parameters for VERITY Transaction Matching Engine."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MatchConfig(BaseModel):
    """Configurable matching tolerances, thresholds, and search bounds."""
    date_tolerance_days: int = Field(
        default=7,
        ge=0,
        description="Maximum allowed difference in days between invoice/claim date and ledger transaction settlement"
    )
    max_combination_size: int = Field(
        default=5,
        ge=2,
        le=10,
        description="Maximum number of candidate records to consider for multi-item combination sums (1:N or N:1)"
    )
    min_score_matched: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Minimum score to classify a relationship as MATCHED"
    )
    min_score_probable: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
        description="Minimum score to classify a relationship as PROBABLE"
    )
    ambiguity_delta_threshold: float = Field(
        default=0.15,
        ge=0.0,
        le=0.5,
        description="Score margin below which competing candidate relationships must remain AMBIGUOUS"
    )
    amount_tolerance_abs: float = Field(
        default=0.0,
        ge=0.0,
        description="Allowable absolute currency discrepancy in INR (e.g. minor bank fee rounding)"
    )
