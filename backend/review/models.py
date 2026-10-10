"""Strongly typed domain models for the VERITY Human Review & Audit Subsystem."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    """Lifecycle status of a human case investigation."""
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class ReviewDecision(str, Enum):
    """Human reviewer verdict on a case (does NOT alter deterministic reconciliation math)."""
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"
    ESCALATED = "ESCALATED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    UNRESOLVED = "UNRESOLVED"


class ReviewActionType(str, Enum):
    """Types of investigation tasks assigned during human review."""
    REVIEW_EVIDENCE = "REVIEW_EVIDENCE"
    VERIFY_ENTITY = "VERIFY_ENTITY"
    VERIFY_TRANSACTION = "VERIFY_TRANSACTION"
    INVESTIGATE_CONTRADICTION = "INVESTIGATE_CONTRADICTION"
    REQUEST_EVIDENCE = "REQUEST_EVIDENCE"
    CONTACT_COUNTERPARTY = "CONTACT_COUNTERPARTY"
    ESCALATE_CASE = "ESCALATE_CASE"
    RECHECK_CASE = "RECHECK_CASE"
    CLOSE_REVIEW = "CLOSE_REVIEW"


class ReviewActionStatus(str, Enum):
    """Execution status of an individual review task."""
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ReviewNote(BaseModel):
    """An append-only timestamped note recorded by a human reviewer."""
    note_id: str = Field(..., description="Unique note identifier")
    reviewer_id: str = Field(..., description="User ID of the reviewer")
    reviewer_name: str = Field(default="Finance Controller", description="Name of the reviewer")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    content: str = Field(..., min_length=1, description="Text content of the review note")


class EvidenceReviewRecord(BaseModel):
    """Audit record indicating an individual evidence artifact was inspected."""
    evidence_id: str = Field(..., description="ID of the reviewed evidence")
    reviewer_id: str = Field(..., description="Reviewer who inspected the artifact")
    reviewer_name: str = Field(default="Finance Controller", description="Reviewer display name")
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Inspection timestamp")
    notes: Optional[str] = Field(default=None, description="Review notes specific to this artifact")


class ReviewAction(BaseModel):
    """A granular investigation action assigned within a case review."""
    action_id: str = Field(..., description="Unique action identifier")
    action_type: ReviewActionType = Field(..., description="Classification of action")
    title: str = Field(..., description="Concise task title")
    description: str = Field(default="", description="Detailed instruction")
    priority: int = Field(default=1, description="Priority rank (1=highest)")
    status: ReviewActionStatus = Field(default=ReviewActionStatus.PENDING, description="Action status")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = Field(default=None)
    reviewer_id: Optional[str] = Field(default=None)
    supporting_ids: List[str] = Field(default_factory=list, description="Linked evidence/claim/txn/disc IDs")
    notes: Optional[str] = Field(default=None, description="Completion notes")


class AuditEventType(str, Enum):
    """Categorized immutable audit lifecycle events."""
    REVIEW_CREATED = "REVIEW_CREATED"
    REVIEW_STARTED = "REVIEW_STARTED"
    EVIDENCE_REVIEWED = "EVIDENCE_REVIEWED"
    NOTE_ADDED = "NOTE_ADDED"
    ACTION_CREATED = "ACTION_CREATED"
    ACTION_COMPLETED = "ACTION_COMPLETED"
    DECISION_RECORDED = "DECISION_RECORDED"
    CASE_ESCALATED = "CASE_ESCALATED"
    REVIEW_RESOLVED = "REVIEW_RESOLVED"
    REVIEW_CLOSED = "REVIEW_CLOSED"


class AuditEvent(BaseModel):
    """An immutable, tamper-evident audit record in the review hash-chain."""
    event_id: str = Field(..., description="Unique event identifier")
    case_id: str = Field(..., description="Associated case ID")
    review_id: str = Field(..., description="Associated review ID")
    event_type: AuditEventType = Field(..., description="Type of audit event")
    actor_id: str = Field(default="system", description="Identifier of user or system agent")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    description: str = Field(..., description="Human-readable audit log description")
    affected_ids: List[str] = Field(default_factory=list, description="IDs of affected domain items")
    previous_state_hash: Optional[str] = Field(default=None, description="SHA-256 hash of preceding audit event")
    current_state_hash: str = Field(..., description="Cryptographic SHA-256 digest of this event state")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReviewRecord(BaseModel):
    """The authoritative human review record for a financial case."""
    review_id: str = Field(..., description="Unique review identifier")
    case_id: str = Field(..., description="Associated case ID")
    status: ReviewStatus = Field(default=ReviewStatus.PENDING, description="Current workflow status")
    decision: Optional[ReviewDecision] = Field(default=None, description="Human reviewer verdict")
    reviewer_id: Optional[str] = Field(default=None, description="Assigned controller ID")
    reviewer_name: Optional[str] = Field(default=None, description="Assigned controller name")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

    # Append-only notes & evidence inspections
    notes: List[ReviewNote] = Field(default_factory=list)
    reviewed_evidence: List[EvidenceReviewRecord] = Field(default_factory=list)
    reviewed_evidence_ids: List[str] = Field(default_factory=list)
    reviewed_claim_ids: List[str] = Field(default_factory=list)
    reviewed_transaction_ids: List[str] = Field(default_factory=list)
    reviewed_discrepancy_ids: List[str] = Field(default_factory=list)
    selected_recommendation_ids: List[str] = Field(default_factory=list)

    # Investigation tasks
    actions: List[ReviewAction] = Field(default_factory=list)
    unresolved_reasons: List[str] = Field(default_factory=list)
    escalation_reason: Optional[str] = Field(default=None)
    provenance_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# -------------------------------------------------------------
# API REQUEST & RESPONSE MODELS
# -------------------------------------------------------------

class StartReviewRequest(BaseModel):
    reviewer_id: str = Field(default="controller_1", description="ID of reviewer starting review")
    reviewer_name: str = Field(default="Finance Controller", description="Name of reviewer")


class AddNoteRequest(BaseModel):
    reviewer_id: str = Field(default="controller_1")
    reviewer_name: str = Field(default="Finance Controller")
    content: str = Field(..., min_length=1, max_length=5000, description="Note content")


class EvidenceReviewRequest(BaseModel):
    reviewer_id: str = Field(default="controller_1")
    reviewer_name: str = Field(default="Finance Controller")
    notes: Optional[str] = Field(default=None, max_length=2000)


class CreateActionRequest(BaseModel):
    action_type: ReviewActionType = Field(default=ReviewActionType.REVIEW_EVIDENCE)
    title: str = Field(..., min_length=2, max_length=200)
    description: str = Field(default="", max_length=1000)
    priority: int = Field(default=1, ge=1, le=10)
    supporting_ids: List[str] = Field(default_factory=list)
    reviewer_id: Optional[str] = Field(default="controller_1")


class CompleteActionRequest(BaseModel):
    reviewer_id: str = Field(default="controller_1")
    notes: Optional[str] = Field(default=None, max_length=2000)


class RecordDecisionRequest(BaseModel):
    decision: ReviewDecision = Field(..., description="Human review verdict")
    reviewer_id: str = Field(default="controller_1")
    reviewer_name: str = Field(default="Finance Controller")
    notes: Optional[str] = Field(default=None, max_length=2000)


class EscalateReviewRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=2000, description="Escalation justification")
    reviewer_id: str = Field(default="controller_1")
    reviewer_name: str = Field(default="Finance Controller")


class ResolveReviewRequest(BaseModel):
    reviewer_id: str = Field(default="controller_1")
    reviewer_name: str = Field(default="Finance Controller")
    notes: Optional[str] = Field(default=None, max_length=2000)


class CloseReviewRequest(BaseModel):
    reviewer_id: str = Field(default="controller_1")
    reviewer_name: str = Field(default="Finance Controller")
    notes: Optional[str] = Field(default=None, max_length=2000)


class ReviewSummaryResponse(BaseModel):
    """Synthesized summary distinguishing deterministic truth from human decisions."""
    case_id: str
    deterministic_status: str
    controller_risk_level: str
    review_status: ReviewStatus
    review_decision: Optional[ReviewDecision]
    requires_human_review: bool
    reviewer_id: Optional[str]
    reviewer_name: Optional[str]
    duration_seconds: float
    audit_event_count: int
    evidence_reviewed_count: int
    total_actions_count: int
    completed_actions_count: int
    pending_actions_count: int
    unresolved_items: List[str]
    notes_count: int


class AuditChainVerificationResponse(BaseModel):
    """Result of verifying cryptographic hash-chain integrity."""
    case_id: str
    is_valid: bool
    event_count: int
    root_hash: Optional[str]
    latest_hash: Optional[str]
    details: str
