"""Result models for VERITY Contradiction Detection Subsystem."""

from __future__ import annotations

from typing import Any, Dict, List
from pydantic import BaseModel, Field

from backend.domain.discrepancy import Discrepancy, DiscrepancySeverity, DiscrepancyType


class ContradictionResult(BaseModel):
    """Aggregate result holding all detected financial contradictions and discrepancies."""
    discrepancies: List[Discrepancy] = Field(
        default_factory=list,
        description="All detected contradiction and discrepancy records"
    )
    total_contradictions: int = Field(default=0, description="Total number of discrepancies detected")
    critical_count: int = Field(default=0, description="Count of CRITICAL severity contradictions")
    error_count: int = Field(default=0, description="Count of ERROR severity contradictions")
    warning_count: int = Field(default=0, description="Count of WARNING severity contradictions")
    info_count: int = Field(default=0, description="Count of INFO severity notices")
    by_type: Dict[str, int] = Field(default_factory=dict, description="Count breakdown by DiscrepancyType")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic metrics")
