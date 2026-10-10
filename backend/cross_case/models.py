"""Domain models for Cross-Case Intelligence & Counterparty Memory (Day 18).

Provides strongly typed Pydantic models for historical counterparty profiles,
reference/UTR reuse correlations, recurring discrepancy patterns, and
deterministic cross-case relationships.

Strict Invariants:
1. All signals and correlations are deterministic facts derived from SQL records.
2. Cross-case intelligence MUST NEVER mutate deterministic financial truth.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CorrelationRelationshipType(str, Enum):
    """Deterministic relationship types between historical cases."""
    SHARED_ENTITY = "SHARED_ENTITY"
    SHARED_REFERENCE = "SHARED_REFERENCE"
    RECURRING_DISCREPANCY = "RECURRING_DISCREPANCY"
    SHARED_EVIDENCE_HASH = "SHARED_EVIDENCE_HASH"


class CounterpartyHistory(BaseModel):
    """Historical profile and multi-case exposure of a counterparty entity."""
    entity_id: str = Field(..., description="Canonical entity ID")
    canonical_name: str = Field(..., description="Canonical counterparty name")
    aliases: List[str] = Field(default_factory=list, description="Known trade names and aliases")
    gstin: Optional[str] = Field(default=None, description="GSTIN identifier if known")
    pan: Optional[str] = Field(default=None, description="PAN identifier if known")
    upi_id: Optional[str] = Field(default=None, description="UPI VPA identifier if known")
    phone: Optional[str] = Field(default=None, description="Contact phone if known")
    case_count: int = Field(default=0, ge=0, description="Total historical cases involving this counterparty")
    total_exposure: float = Field(default=0.0, ge=0.0, description="Sum of expected/claimed amounts across cases")
    disputed_exposure: float = Field(default=0.0, ge=0.0, description="Sum of disputed/contradicted amounts across cases")
    unresolved_exposure: float = Field(default=0.0, ge=0.0, description="Sum of outstanding balances across cases")
    contradiction_count: int = Field(default=0, ge=0, description="Number of cases with CONTRADICTED status")
    previous_case_ids: List[str] = Field(default_factory=list, description="List of all associated case IDs")
    discrepancy_types: List[str] = Field(default_factory=list, description="Unique discrepancy types encountered")
    first_seen: Optional[str] = Field(default=None, description="Earliest case timestamp")
    last_seen: Optional[str] = Field(default=None, description="Most recent case timestamp")
    historical_risk_signals: List[str] = Field(default_factory=list, description="Deterministic risk alerts")


class ReferenceCorrelation(BaseModel):
    """Cross-case correlation for a bank reference, UTR, or RRN."""
    reference_id: str = Field(..., description="Bank reference, UTR, RRN, or cheque number")
    current_case_id: Optional[str] = Field(default=None, description="Context case ID if querying from a case")
    previous_case_ids: List[str] = Field(default_factory=list, description="All cases where this reference appeared")
    transaction_ids: List[str] = Field(default_factory=list, description="Transactions citing this reference")
    claim_ids: List[str] = Field(default_factory=list, description="Claims citing this reference hint")
    occurrence_count: int = Field(default=0, ge=0, description="Total distinct cases citing this reference")
    reuse_warning: bool = Field(default=False, description="True if reference appears in more than one distinct case")
    related_amounts: List[float] = Field(default_factory=list, description="Amounts associated with this reference")
    related_dates: List[str] = Field(default_factory=list, description="Timestamps associated with this reference")


class RecurringDiscrepancyPattern(BaseModel):
    """Pattern analysis of recurring discrepancy types for a counterparty or portfolio."""
    entity_name: Optional[str] = Field(default=None, description="Entity canonical name if entity-scoped")
    discrepancy_type: str = Field(..., description="Category of discrepancy (e.g. AMOUNT_MISMATCH)")
    occurrence_count: int = Field(default=0, ge=0, description="Number of times this discrepancy occurred")
    affected_case_ids: List[str] = Field(default_factory=list, description="Case IDs containing this discrepancy")
    total_affected_exposure: float = Field(default=0.0, ge=0.0, description="Total financial volume of affected cases")
    severity_distribution: Dict[str, int] = Field(default_factory=dict, description="Count per severity level")
    sample_messages: List[str] = Field(default_factory=list, description="Sample human-readable discrepancy messages")


class CrossCaseCorrelation(BaseModel):
    """Explicit deterministic link between two financial cases."""
    current_case_id: str = Field(..., description="Current case being analyzed")
    related_case_id: str = Field(..., description="Historical case related to current case")
    relationship_type: CorrelationRelationshipType = Field(..., description="Nature of the connection")
    shared_identifier: str = Field(..., description="Shared entity name, UTR, or hash")
    deterministic_reason: str = Field(..., description="Human-verifiable reason explaining the link")
    supporting_ids: List[str] = Field(default_factory=list, description="IDs of matching entities, txns, or claims")
    related_case_status: Optional[str] = Field(default=None, description="Deterministic truth status of related case")
    related_case_amount: Optional[float] = Field(default=None, description="Total exposure of related case")


class HistoricalRiskSignal(BaseModel):
    """Deterministic, explainable risk warning derived from historical patterns."""
    signal_type: str = Field(..., description="Machine identifier (e.g. REPEAT_CONTRADICTION)")
    severity: str = Field(..., description="INFO, WARNING, or CRITICAL")
    title: str = Field(..., description="Short headline summary")
    description: str = Field(..., description="Deterministic factual explanation")
    affected_case_ids: List[str] = Field(default_factory=list, description="Cases providing evidence for this signal")
    supporting_ids: List[str] = Field(default_factory=list, description="Supporting transaction, entity, or ref IDs")


class CaseIntelligenceProfile(BaseModel):
    """Unified cross-case intelligence dossier for a single case."""
    case_id: str = Field(..., description="Target case ID")
    counterparty_histories: List[CounterpartyHistory] = Field(default_factory=list)
    reference_correlations: List[ReferenceCorrelation] = Field(default_factory=list)
    recurring_discrepancies: List[RecurringDiscrepancyPattern] = Field(default_factory=list)
    related_cases: List[CrossCaseCorrelation] = Field(default_factory=list)
    historical_risk_signals: List[HistoricalRiskSignal] = Field(default_factory=list)
