"""VERITY Persistent Data Models & Persistence Schemas (Day 16).

Defines strongly typed persistence models across all pipeline stages, ensuring
deterministic immutability boundaries for financial records, append-only guarantees
for audit logs, and clear separation between operational state and financial truth.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -------------------------------------------------------------
# 1. CORE CASE & PIPELINE RECORD
# -------------------------------------------------------------
class CaseRecord(BaseModel):
    """Authoritative persistent record of an executed case."""
    case_id: str = Field(..., description="Unique case identifier (Primary Key)")
    status: str = Field(..., description="Deterministic synthesized status (CONFIRMED, CONTRADICTED, etc.)")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    total_execution_time_ms: float = Field(default=0.0)
    financial_summary: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: str = Field(default_factory=_utc_now_iso)


# -------------------------------------------------------------
# 2. EVIDENCE & EXTRACTION RECORDS (IMMUTABLE)
# -------------------------------------------------------------
class EvidenceRecord(BaseModel):
    """Immutable persistent record of ingested raw evidence."""
    id: str = Field(..., description="Evidence ID")
    case_id: str = Field(..., description="Parent case ID")
    modality: str = Field(..., description="INVOICE, BANK_STATEMENT, MESSAGING_CHAT, PAYMENT_SCREENSHOT, etc.")
    source_name: Optional[str] = Field(default=None)
    source_type: Optional[str] = Field(default=None)
    sha256_hash: str = Field(..., description="SHA-256 fingerprint of original content")
    summary: str = Field(default="")
    raw_payload: str = Field(default="")
    created_at: str = Field(default_factory=_utc_now_iso)


class ClaimRecord(BaseModel):
    """Immutable persistent record of an extracted financial claim."""
    id: str = Field(..., description="Claim ID")
    case_id: str = Field(..., description="Parent case ID")
    evidence_id: str = Field(..., description="Parent evidence ID")
    claim_type: str = Field(..., description="INVOICE_ISSUED, PAYMENT_SENT, etc.")
    claimed_amount: Optional[float] = Field(default=None)
    claimed_date: Optional[str] = Field(default=None)
    counterparty_hint: Optional[str] = Field(default=None)
    reference_id_hint: Optional[str] = Field(default=None)
    confidence: float = Field(default=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utc_now_iso)


class EntityRecord(BaseModel):
    """Persistent record of a resolved entity."""
    id: str = Field(..., description="Entity ID")
    case_id: str = Field(..., description="Parent case ID")
    canonical_name: str = Field(...)
    entity_type: Optional[str] = Field(default=None)
    gstin: Optional[str] = Field(default=None)
    pan: Optional[str] = Field(default=None)
    upi_id: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    aliases: List[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0)
    resolved_via: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utc_now_iso)


class TransactionRecord(BaseModel):
    """Immutable persistent record of a bank ledger transaction."""
    id: str = Field(..., description="Transaction ID")
    case_id: str = Field(..., description="Parent case ID")
    amount: float = Field(...)
    direction: str = Field(...)
    timestamp: Optional[str] = Field(default=None)
    bank_reference: Optional[str] = Field(default=None)
    payment_method: Optional[str] = Field(default=None)
    counterparty_entity_id: Optional[str] = Field(default=None)
    account_number_mask: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utc_now_iso)


# -------------------------------------------------------------
# 3. MATCHING, DEDUPLICATION & CONTRADICTIONS
# -------------------------------------------------------------
class MatchRelationshipRecord(BaseModel):
    """Persistent record of a Day 5 transaction match."""
    id: str = Field(...)
    case_id: str = Field(...)
    relationship_type: str = Field(...)
    status: str = Field(...)
    source_claim_ids: List[str] = Field(default_factory=list)
    target_transaction_ids: List[str] = Field(default_factory=list)
    matched_amount: float = Field(default=0.0)
    target_amount: float = Field(default=0.0)
    score: float = Field(default=1.0)
    matched_signals: List[str] = Field(default_factory=list)
    conflicting_signals: List[str] = Field(default_factory=list)
    explanation: str = Field(default="")
    created_at: str = Field(default_factory=_utc_now_iso)


class DeduplicationGroupRecord(BaseModel):
    """Persistent record of a Day 6 cross-modal deduplication group."""
    id: str = Field(...)
    case_id: str = Field(...)
    group_type: str = Field(...)
    member_evidence_ids: List[str] = Field(default_factory=list)
    member_claim_ids: List[str] = Field(default_factory=list)
    canonical_event_id: Optional[str] = Field(default=None)
    confidence: float = Field(default=1.0)
    reason: str = Field(default="")
    created_at: str = Field(default_factory=_utc_now_iso)


class DiscrepancyRecord(BaseModel):
    """Persistent record of a Day 7 detected discrepancy/contradiction."""
    id: str = Field(...)
    case_id: str = Field(...)
    discrepancy_type: str = Field(...)
    severity: str = Field(...)
    message: str = Field(...)
    expected_value: Optional[str] = Field(default=None)
    observed_value: Optional[str] = Field(default=None)
    involved_evidence_ids: List[str] = Field(default_factory=list)
    involved_claim_ids: List[str] = Field(default_factory=list)
    involved_transaction_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utc_now_iso)


# -------------------------------------------------------------
# 4. RECONCILIATION & REPORTING (DETERMINISTIC TRUTH)
# -------------------------------------------------------------
class ReconciliationRecordModel(BaseModel):
    """Persistent record of a Day 8 reconciliation result."""
    reconciliation_id: str = Field(...)
    case_id: str = Field(...)
    status: str = Field(...)
    event_id: Optional[str] = Field(default=None)
    entity_id: Optional[str] = Field(default=None)
    claim_ids: List[str] = Field(default_factory=list)
    transaction_ids: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    expected_amount: Optional[float] = Field(default=None)
    matched_amount: float = Field(default=0.0)
    outstanding_amount: float = Field(default=0.0)
    currency: str = Field(default="INR")
    confidence_score: float = Field(default=1.0)
    supporting_signals: List[str] = Field(default_factory=list)
    contradicting_signals: List[str] = Field(default_factory=list)
    discrepancy_ids: List[str] = Field(default_factory=list)
    match_relationship_ids: List[str] = Field(default_factory=list)
    deduplication_group_ids: List[str] = Field(default_factory=list)
    explanation: str = Field(default="")
    reason_codes: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utc_now_iso)


class TruthReportRecord(BaseModel):
    """Persistent record of a Day 9 Financial Truth Report."""
    case_id: str = Field(...)
    title: str = Field(default="")
    summary: str = Field(default="")
    text_report: str = Field(default="")
    status: str = Field(...)
    confidence_score: float = Field(default=1.0)
    financial_summary: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    requires_human_review: bool = Field(default=False)
    report_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utc_now_iso)


# -------------------------------------------------------------
# 5. CONTROLLER & OPERATIONAL REVIEW
# -------------------------------------------------------------
class ControllerDecisionRecord(BaseModel):
    """Persistent record of Day 13 AI Controller decisions."""
    case_id: str = Field(...)
    risk_level: str = Field(...)
    decision: str = Field(...)
    requires_human_review: bool = Field(default=False)
    confidence: float = Field(default=1.0)
    reasons: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    executive_brief: str = Field(default="")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utc_now_iso)


class ReviewRecordModel(BaseModel):
    """Persistent record of Day 14 Human Review workspace state."""
    review_id: str = Field(...)
    case_id: str = Field(...)
    status: str = Field(default="PENDING")
    decision: Optional[str] = Field(default=None)
    assigned_to: Optional[str] = Field(default=None)
    required_actions: List[str] = Field(default_factory=list)
    completed_actions: List[str] = Field(default_factory=list)
    notes_count: int = Field(default=0)
    inspected_evidence_count: int = Field(default=0)
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: str = Field(default_factory=_utc_now_iso)
    closed_at: Optional[str] = Field(default=None)


class ReviewNoteRecord(BaseModel):
    """Persistent record of an append-only review note."""
    note_id: str = Field(...)
    case_id: str = Field(...)
    review_id: str = Field(...)
    author_id: str = Field(...)
    author_name: str = Field(...)
    note_type: str = Field(default="OBSERVATION")
    content: str = Field(...)
    timestamp: str = Field(default_factory=_utc_now_iso)


class EvidenceReviewRecordModel(BaseModel):
    """Persistent record of an evidence inspection."""
    inspection_id: str = Field(...)
    case_id: str = Field(...)
    review_id: str = Field(...)
    evidence_id: str = Field(...)
    reviewer_id: str = Field(...)
    verified: bool = Field(default=True)
    notes: Optional[str] = Field(default=None)
    timestamp: str = Field(default_factory=_utc_now_iso)


# -------------------------------------------------------------
# 6. AUDIT TRAIL & HASH CHAIN (APPEND-ONLY)
# -------------------------------------------------------------
class AuditEventRecord(BaseModel):
    """Persistent, tamper-evident audit event bound into a SHA-256 hash chain."""
    event_id: str = Field(...)
    case_id: str = Field(...)
    review_id: Optional[str] = Field(default=None)
    event_type: str = Field(...)
    actor_id: str = Field(...)
    timestamp: str = Field(default_factory=_utc_now_iso)
    description: str = Field(...)
    affected_ids: List[str] = Field(default_factory=list)
    previous_state_hash: str = Field(...)
    current_state_hash: str = Field(...)
    sequence_number: int = Field(default=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# -------------------------------------------------------------
# 7. CASE PORTFOLIO & ASSIGNMENTS
# -------------------------------------------------------------
class CaseAssignmentRecord(BaseModel):
    """Persistent record of reviewer assignment."""
    case_id: str = Field(...)
    reviewer_id: str = Field(...)
    reviewer_name: str = Field(...)
    assigned_at: str = Field(default_factory=_utc_now_iso)
    unassigned_at: Optional[str] = Field(default=None)
    active: bool = Field(default=True)


class PortfolioStateRecord(BaseModel):
    """Persistent operational portfolio state for a case."""
    case_id: str = Field(...)
    portfolio_status: str = Field(default="NEW")
    priority: str = Field(default="LOW")
    priority_score: float = Field(default=0.0)
    priority_reasons: List[str] = Field(default_factory=list)
    amount_exposure: float = Field(default=0.0)
    disputed_amount: float = Field(default=0.0)
    unresolved_amount: float = Field(default=0.0)
    sla_status: str = Field(default="ON_TRACK")
    sla_due_at: Optional[str] = Field(default=None)
    sla_elapsed_hours: float = Field(default=0.0)
    sla_remaining_hours: float = Field(default=0.0)
    assigned_reviewer_id: Optional[str] = Field(default=None)
    assigned_reviewer_name: Optional[str] = Field(default=None)
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: str = Field(default_factory=_utc_now_iso)


# -------------------------------------------------------------
# 8. IDEMPOTENCY RECORD
# -------------------------------------------------------------
class IdempotencyRecord(BaseModel):
    """Persistent idempotency lock preventing duplicate processing executions."""
    key: str = Field(..., description="Idempotency key or case_id hash")
    case_id: str = Field(...)
    request_hash: str = Field(..., description="SHA-256 fingerprint of the request payload")
    response_reference: Optional[str] = Field(default=None)
    status: str = Field(default="COMPLETED")
    created_at: str = Field(default_factory=_utc_now_iso)
