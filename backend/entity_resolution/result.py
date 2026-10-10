"""Result and candidate models for VERITY Entity Resolution Subsystem."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.domain.entity import Entity


class EntityResolutionStatus(str, Enum):
    """Resolution confidence status."""
    CONFIRMED = "CONFIRMED"         # Unambiguous high-confidence match on strong identifier or combined signals
    PROBABLE = "PROBABLE"           # Strong name / alias match without conflicting identifiers
    AMBIGUOUS = "AMBIGUOUS"         # Multiple viable candidates with no distinguishing identifier (Do NOT merge!)
    CONFLICTING = "CONFLICTING"     # Conflicting identity signals detected (e.g. matching phone but conflicting VPA)
    UNRESOLVED = "UNRESOLVED"       # No candidate found or insufficient identity signals present


class EntityCandidate(BaseModel):
    """A scored candidate entity matching an identity query or claim."""
    entity_id: str = Field(..., description="ID of the candidate Entity")
    canonical_name: str = Field(..., description="Canonical name of the candidate Entity")
    score: float = Field(..., ge=0.0, le=1.0, description="Match score (0.0 to 1.0)")
    matched_signals: List[str] = Field(default_factory=list, description="List of positive matching signals")
    conflicting_signals: List[str] = Field(default_factory=list, description="List of contradictory signals")
    explanation: str = Field(..., description="Human-readable justification for this candidate's score")


class EntityResolutionResult(BaseModel):
    """Container holding the final entity resolution outcome for a Claim or query."""
    claim_id: Optional[str] = Field(None, description="ID of the source Claim if resolving a claim")
    status: EntityResolutionStatus = Field(..., description="Resolution outcome status")
    selected_entity_id: Optional[str] = Field(
        default=None,
        description="ID of the resolved Entity (must be NULL if AMBIGUOUS, CONFLICTING, or UNRESOLVED)"
    )
    selected_entity: Optional[Entity] = Field(
        default=None,
        description="The resolved Entity instance if uniquely resolved"
    )
    score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for the selected candidate or highest candidate"
    )
    candidates: List[EntityCandidate] = Field(
        default_factory=list,
        description="Ranked list of evaluated entity candidates"
    )
    matched_signals: List[str] = Field(
        default_factory=list,
        description="Aggregated list of positive matching signals"
    )
    conflicting_signals: List[str] = Field(
        default_factory=list,
        description="Aggregated list of conflicting signals"
    )
    explanation: str = Field(..., description="Transparent explanation of the resolution decision")
    warnings: List[str] = Field(default_factory=list, description="Diagnostic warnings")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional resolution diagnostics")
