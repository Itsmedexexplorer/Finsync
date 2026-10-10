"""Input and execution models for VERITY End-to-End Case Processing Pipeline."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from backend.domain.entity import Entity
from backend.domain.evidence import Evidence
from backend.domain.transaction import Transaction


class PipelineStage(str, Enum):
    """The 8 sequential stages of the VERITY Finance Controller Pipeline."""
    INGESTION = "INGESTION"
    EXTRACTION = "EXTRACTION"
    ENTITY_RESOLUTION = "ENTITY_RESOLUTION"
    TRANSACTION_MATCHING = "TRANSACTION_MATCHING"
    DEDUPLICATION = "DEDUPLICATION"
    CONTRADICTION_DETECTION = "CONTRADICTION_DETECTION"
    RECONCILIATION = "RECONCILIATION"
    REPORTING = "REPORTING"


class StageExecutionRecord(BaseModel):
    """Diagnostic execution telemetry for an individual pipeline stage."""
    stage: PipelineStage = Field(..., description="Pipeline stage executed")
    status: str = Field(default="SUCCESS", description="SUCCESS, SKIPPED, or ERROR")
    duration_ms: float = Field(default=0.0, description="Stage latency in milliseconds")
    items_in: int = Field(default=0, description="Count of input items processed")
    items_out: int = Field(default=0, description="Count of output items generated")
    notes: Optional[str] = Field(default=None, description="Optional diagnostic notes or error trace")


class CaseInput(BaseModel):
    """Canonical input representation for a financial reconciliation case."""
    case_id: str = Field(..., description="Unique case identifier, e.g. CASE-2026-001")
    
    # Pre-normalized domain inputs
    evidence_items: List[Evidence] = Field(default_factory=list, description="Pre-ingested Evidence objects")
    transactions: List[Transaction] = Field(default_factory=list, description="Verified bank ledger transactions")
    entities: List[Entity] = Field(default_factory=list, description="Known counterparty entities")
    
    # Raw unparsed file/text inputs
    raw_file_paths: List[str] = Field(default_factory=list, description="Local file paths to ingest (CSV, PDF, Images, Text)")
    raw_text_messages: List[Dict[str, Any]] = Field(default_factory=list, description="Raw text/WhatsApp payloads with metadata")
    
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary case metadata")
