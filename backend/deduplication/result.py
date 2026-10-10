"""Result and group models for VERITY Cross-Modal Deduplication Subsystem.

Represents event grouping and content deduplication without destroying underlying evidence.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DeduplicationStatus(str, Enum):
    """Classification status of a deduplication group."""
    SAME_EVENT = "SAME_EVENT"                           # Multiple evidence items describe the exact same financial event
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"           # Plausible duplicate event with partial signals or minor discrepancy
    DUPLICATE_EVIDENCE_CONTENT = "DUPLICATE_EVIDENCE_CONTENT" # Identical cryptographic payload uploaded multiple times
    DISTINCT_EVENT = "DISTINCT_EVENT"                   # Standalone distinct financial event
    AMBIGUOUS = "AMBIGUOUS"                             # Multiple competing groupings requiring human review


class DeduplicationGroup(BaseModel):
    """A non-destructive grouping of evidence, claims, and transactions representing an underlying event."""
    group_id: str = Field(..., description="Unique event group identifier, e.g. GRP-2026-001")
    status: DeduplicationStatus = Field(..., description="Deduplication classification status")
    
    # Member references
    member_evidence_ids: List[str] = Field(
        default_factory=list,
        description="IDs of all raw Evidence artifacts grouped into this event"
    )
    member_claim_ids: List[str] = Field(
        default_factory=list,
        description="IDs of all Claim assertions associated with this event"
    )
    candidate_transaction_ids: List[str] = Field(
        default_factory=list,
        description="IDs of all ledger Transactions associated with this event"
    )
    
    # Synthesized event attributes (non-destructive candidate representation)
    canonical_event_candidate: Dict[str, Any] = Field(
        default_factory=dict,
        description="Candidate properties (amount, entity_id, reference, payment_method, date)"
    )
    
    # Scoring & Explainability
    score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Deduplication confidence score (0.0 to 1.0)"
    )
    matched_signals: List[str] = Field(
        default_factory=list,
        description="List of positive matching signals linking members"
    )
    conflicting_signals: List[str] = Field(
        default_factory=list,
        description="List of contradictory signals detected between members"
    )
    explanation: str = Field(..., description="Human-readable justification for this event group")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional technical diagnostics")


class DeduplicationResult(BaseModel):
    """Aggregate result holding all formed deduplication groups and metrics."""
    groups: List[DeduplicationGroup] = Field(
        default_factory=list,
        description="All formed deduplication and event groups"
    )
    distinct_event_count: int = Field(default=0, description="Number of distinct financial events identified")
    content_duplicate_count: int = Field(default=0, description="Number of cryptographic content duplicate groups")
    ambiguous_count: int = Field(default=0, description="Number of ambiguous groupings")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Detailed clustering and grouping metrics")
