"""Pydantic API Request and Response models for the VERITY Finance Controller API."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.domain.entity import Entity
from backend.domain.evidence import Evidence
from backend.domain.transaction import Transaction


class ErrorCode(str, Enum):
    """Stable API error codes."""
    INVALID_INPUT = "INVALID_INPUT"
    UNSUPPORTED_MEDIA = "UNSUPPORTED_MEDIA"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    CASE_NOT_FOUND = "CASE_NOT_FOUND"
    PROCESSING_ERROR = "PROCESSING_ERROR"
    RESOURCE_LIMIT = "RESOURCE_LIMIT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorDetail(BaseModel):
    """Structured error payload details."""
    code: ErrorCode = Field(..., description="Stable machine-readable error code")
    message: str = Field(..., description="Human-readable explanation")
    request_id: str = Field(..., description="Unique request identifier for tracing")


class ErrorResponse(BaseModel):
    """Canonical API error response container."""
    error: ErrorDetail


# -------------------------------------------------------------
# REQUEST MODELS
# -------------------------------------------------------------

class CaseCreateRequest(BaseModel):
    """Payload for submitting a structured financial case to the pipeline."""
    case_id: str = Field(..., description="Unique case identifier, e.g. CASE-2026-001")
    evidence_items: List[Evidence] = Field(default_factory=list, description="Pre-ingested Evidence objects")
    raw_file_paths: List[str] = Field(default_factory=list, description="Local file paths to ingest")
    raw_text_messages: List[Dict[str, Any]] = Field(default_factory=list, description="Raw text/chat payloads")
    transactions: List[Transaction] = Field(default_factory=list, description="Verified bank ledger transactions")
    entities: List[Entity] = Field(default_factory=list, description="Known counterparty entities")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary case metadata")


class TextEvidenceRequest(BaseModel):
    """Payload for processing raw text/messaging evidence."""
    text: str = Field(..., description="Raw text, WhatsApp export snippet, or SMS message")
    source_name: Optional[str] = Field(default="raw_chat_export.txt", description="Source identifier")
    case_id: Optional[str] = Field(default=None, description="Optional custom case ID")


# -------------------------------------------------------------
# RESPONSE MODELS
# -------------------------------------------------------------

class HealthResponse(BaseModel):
    """Health check status response."""
    status: str = Field(default="ok")
    service: str = Field(default="verity")
    version: str = Field(default="day12")


class ReadinessResponse(BaseModel):
    """System readiness check response validating all internal subsystems."""
    status: str = Field(default="ready", description="'ready' or 'unready'")
    service: str = Field(default="verity")
    environment: str = Field(default="development")
    config_valid: bool = Field(default=True)
    case_store_ready: bool = Field(default=True)
    database_ready: bool = Field(default=True)
    audit_store_ready: bool = Field(default=True)
    benchmark_available: bool = Field(default=True)
    pipeline_ready: bool = Field(default=True)
    active_cases_in_memory: int = Field(default=0)
    version: str = Field(default="day16")


class InfoResponse(BaseModel):
    """System information, supported modalities, and pipeline stage capabilities."""
    app_name: str = "VERITY — Financial Truth, Reconstructed"
    version: str = "0.1.0-day11"
    track: str = "AI Finance Controller (Razorpay AI Buildathon 2026)"
    available_pipeline_stages: List[str] = [
        "INGESTION",
        "EXTRACTION",
        "ENTITY_RESOLUTION",
        "TRANSACTION_MATCHING",
        "DEDUPLICATION",
        "CONTRADICTION_DETECTION",
        "RECONCILIATION",
        "REPORTING",
    ]
    supported_modalities: List[str] = [
        "BANK_STATEMENT (CSV)",
        "INVOICE (PDF, Text)",
        "MESSAGING_CHAT (WhatsApp, SMS)",
        "PAYMENT_SCREENSHOT (PNG, JPG)",
        "CASH_VOUCHER",
    ]
    safety_guarantees: List[str] = [
        "Zero LLM hallucination in financial math",
        "Deterministic Indian entity resolution (GSTIN, PAN, UPI, Phone)",
        "Strict uncertainty preservation (AMBIGUOUS, CONTRADICTED never falsely confirmed)",
        "Immutable SHA-256 Provenance DAG trace",
    ]


class FinancialSummaryResponse(BaseModel):
    """Monetary and count metrics from financial reconciliation."""
    claimed_amount: Optional[float] = None
    matched_amount: float = 0.0
    outstanding_amount: float = 0.0
    total_reconciled_batch: float = 0.0
    total_outstanding_batch: float = 0.0
    evidence_count: int = 0
    claims_count: int = 0
    transactions_count: int = 0
    discrepancies_count: int = 0


class StageRecordResponse(BaseModel):
    """Execution telemetry for a single pipeline stage."""
    stage: str
    status: str
    duration_ms: float
    items_in: int
    items_out: int
    notes: Optional[str] = None


class ProvenanceNodeResponse(BaseModel):
    """Single node in the tamper-evident provenance DAG."""
    node_id: str
    node_type: str
    label: str
    content_hash: str
    parent_ids: List[str] = Field(default_factory=list)
    timestamp: str


class ProvenanceGraphResponse(BaseModel):
    """Complete provenance trace linking final truth back to source evidence."""
    case_id: str
    total_nodes: int
    nodes: List[ProvenanceNodeResponse] = Field(default_factory=list)
    root_evidence_ids: List[str] = Field(default_factory=list)


class DemoCaseSummaryResponse(BaseModel):
    """Summary descriptor for pre-packaged demo scenarios."""
    case_id: str
    title: str
    description: str
    expected_status: str
    evidence_modalities: List[str]


class CaseResponse(BaseModel):
    """Unified Case Processing API response matching the Day 11 contract."""
    case_id: str
    status: str
    confidence: float
    requires_review: bool
    financial_summary: FinancialSummaryResponse
    truth_report: Optional[Dict[str, Any]] = None
    stage_execution: List[StageRecordResponse] = Field(default_factory=list)
    provenance: Optional[Dict[str, Any]] = None
    total_execution_time_ms: float = 0.0
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    text_report: str = ""


# -------------------------------------------------------------
# TRACK 04 BENCHMARK BATCH RECONCILIATION MODELS
# -------------------------------------------------------------

class BenchmarkCaseSummary(BaseModel):
    """Concise record summary for a benchmark case in a batch run."""
    case_id: str
    category: str
    scenario_title: str
    status: str
    confidence: float
    claimed_amount: Optional[float] = None
    matched_amount: float = 0.0
    outstanding_amount: float = 0.0
    discrepancy_count: int = 0
    discrepancy_types: List[str] = Field(default_factory=list)
    human_review_required: bool = False
    duration_ms: float = 0.0


class BenchmarkRunResponse(BaseModel):
    """Comprehensive, dynamically computed results for the Track 04 benchmark batch."""
    total_cases: int = Field(..., description="Total synthetic cases evaluated in batch")
    total_evidence_items: int = Field(default=0, description="Total root evidence items processed")
    total_claims: int = Field(default=0, description="Total extracted claims evaluated")
    total_transactions: int = Field(default=0, description="Total ledger transactions verified")
    total_claimed_value: float = Field(default=0.0, description="Cumulative claimed monetary value INR")
    total_reconciled_value: float = Field(default=0.0, description="Cumulative verified reconciled value INR")
    total_outstanding_value: float = Field(default=0.0, description="Cumulative unresolved outstanding balance INR")
    monetary_match_rate: float = Field(default=0.0, description="Calculated percentage value match rate")
    status_distribution: Dict[str, int] = Field(default_factory=dict, description="Counts by reconciliation status")
    exception_breakdown: Dict[str, int] = Field(default_factory=dict, description="Counts of unresolved discrepancy types")
    category_breakdown: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Per-category performance breakdown")
    total_processing_time_ms: float = Field(default=0.0, description="Total batch execution time in ms")
    average_latency_ms: float = Field(default=0.0, description="Average per-case execution latency in ms")
    cases: List[BenchmarkCaseSummary] = Field(default_factory=list, description="Per-case drilldown records")
