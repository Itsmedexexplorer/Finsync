"""VERITY Financial Case Portfolio & Operations Intelligence Domain Models (Day 15).

Provides strongly typed models for portfolio cases, assignments, SLA state,
workload analytics, exposure tracking, filtering, sorting, and pagination.

Strict Invariant:
PORTFOLIO INTELLIGENCE MUST NEVER MODIFY FINANCIAL TRUTH.
OPERATIONAL STATUS != FINANCIAL TRUTH.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PortfolioCaseStatus(str, Enum):
    """Operational status of a case within the portfolio management workflow."""
    NEW = "NEW"
    TRIAGED = "TRIAGED"
    ASSIGNED = "ASSIGNED"
    IN_REVIEW = "IN_REVIEW"
    WAITING_FOR_EVIDENCE = "WAITING_FOR_EVIDENCE"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class PortfolioPriority(str, Enum):
    """Operational urgency priority for financial case triage."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SLAStatus(str, Enum):
    """SLA tracking status based on operational deadlines."""
    ON_TRACK = "ON_TRACK"
    DUE_SOON = "DUE_SOON"
    OVERDUE = "OVERDUE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"


class PortfolioSortField(str, Enum):
    """Field on which portfolio cases can be sorted."""
    PRIORITY = "priority"
    RISK = "risk"
    AMOUNT = "amount"
    AGE = "age"
    SLA = "sla"
    LAST_ACTIVITY = "last_activity"


class SortOrder(str, Enum):
    """Sorting direction."""
    ASC = "asc"
    DESC = "desc"


class CaseAssignment(BaseModel):
    """Operational reviewer assignment record for a financial case."""
    assignment_id: str
    case_id: str
    reviewer_id: str
    reviewer_name: str = "Unassigned"
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assigned_by: str = "system"
    active: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CasePortfolioItem(BaseModel):
    """Authoritative operational summary item for a financial case."""
    case_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Deterministic Core (Immutable Financial Truth)
    deterministic_status: str
    confidence_score: float = 1.0

    # Human Review & Operational Workflow Status
    human_review_status: str = "NOT_REQUIRED"
    human_review_decision: Optional[str] = None
    portfolio_status: PortfolioCaseStatus = PortfolioCaseStatus.NEW

    # Intelligence & Risk Layer
    risk_level: str = "LOW"
    priority: PortfolioPriority = PortfolioPriority.LOW
    primary_action: str = "CONFIRM_RECONCILIATION"
    requires_human_review: bool = False

    # Reviewer Assignment
    assigned_reviewer_id: Optional[str] = None
    assigned_reviewer_name: Optional[str] = None

    # SLA Tracking
    sla_status: SLAStatus = SLAStatus.ON_TRACK
    sla_due_at: Optional[datetime] = None
    sla_window_hours: float = 72.0

    # Canonical Monetary Exposure (Zero Double-Counting)
    amount_exposure: float = 0.0
    disputed_amount: float = 0.0
    unresolved_amount: float = 0.0
    partial_amount: float = 0.0
    matched_amount: float = 0.0

    # Domain Entity & Provenance Lineage References
    entity_ids: List[str] = Field(default_factory=list)
    transaction_ids: List[str] = Field(default_factory=list)
    discrepancy_ids: List[str] = Field(default_factory=list)
    evidence_count: int = 0
    claim_count: int = 0
    transaction_count: int = 0
    unresolved_issue_count: int = 0

    # Lineage & Audit
    source_case_id: str
    last_activity_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    title: Optional[str] = None
    summary: Optional[str] = None


class PortfolioPriorityScore(BaseModel):
    """Deterministic score and breakdown for portfolio case prioritization."""
    case_id: str
    score: float
    priority: PortfolioPriority
    reasons: List[str] = Field(default_factory=list)
    supporting_case_id: str
    discrepancy_ids: List[str] = Field(default_factory=list)
    transaction_ids: List[str] = Field(default_factory=list)


class PortfolioExposure(BaseModel):
    """Portfolio-wide financial exposure synthesis."""
    total_exposure: float = 0.0
    disputed_exposure: float = 0.0
    unresolved_exposure: float = 0.0
    partial_exposure: float = 0.0
    confirmed_exposure: float = 0.0
    exposure_by_risk: Dict[str, float] = Field(default_factory=dict)
    exposure_by_status: Dict[str, float] = Field(default_factory=dict)


class PortfolioSummary(BaseModel):
    """Executive portfolio-wide operational health summary."""
    total_cases: int = 0
    new_cases: int = 0
    open_cases: int = 0
    in_review_cases: int = 0
    waiting_for_evidence_cases: int = 0
    escalated_cases: int = 0
    resolved_cases: int = 0
    closed_cases: int = 0

    critical_cases: int = 0
    high_risk_cases: int = 0
    medium_risk_cases: int = 0
    low_risk_cases: int = 0

    total_exposure: float = 0.0
    total_disputed_amount: float = 0.0
    total_unresolved_amount: float = 0.0
    total_partial_amount: float = 0.0

    overdue_cases: int = 0
    due_soon_cases: int = 0
    assigned_cases: int = 0
    unassigned_cases: int = 0


class PortfolioFilter(BaseModel):
    """Filter criteria for querying the portfolio case index."""
    status: Optional[PortfolioCaseStatus] = None
    priority: Optional[PortfolioPriority] = None
    risk_level: Optional[str] = None
    reviewer_id: Optional[str] = None
    deterministic_status: Optional[str] = None
    human_review_status: Optional[str] = None
    sla_status: Optional[SLAStatus] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    entity_id: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search: Optional[str] = None


class PortfolioSort(BaseModel):
    """Sort specification for portfolio queries."""
    field: PortfolioSortField = PortfolioSortField.PRIORITY
    order: SortOrder = SortOrder.DESC


class PortfolioPage(BaseModel):
    """Paginated result of a portfolio query."""
    items: List[CasePortfolioItem]
    total: int
    page: int
    page_size: int
    total_pages: int
    applied_filters: Dict[str, Any] = Field(default_factory=dict)
    sort: Dict[str, Any] = Field(default_factory=dict)


class PortfolioWorkload(BaseModel):
    """Reviewer-centric workload and capacity allocation metrics."""
    reviewer_id: str
    reviewer_name: str
    assigned_cases: int = 0
    open_cases: int = 0
    critical_cases: int = 0
    overdue_cases: int = 0
    total_exposure: float = 0.0
    is_overloaded: bool = False
    overload_reasons: List[str] = Field(default_factory=list)


# API Request / Response Models
class AssignCaseRequest(BaseModel):
    reviewer_id: str
    reviewer_name: Optional[str] = None
    assigned_by: str = "controller_admin"


class ReassignCaseRequest(BaseModel):
    new_reviewer_id: str
    new_reviewer_name: Optional[str] = None
    reassigned_by: str = "controller_admin"
    reason: Optional[str] = None


class UnassignCaseRequest(BaseModel):
    unassigned_by: str = "controller_admin"
    reason: Optional[str] = None
