"""Final Result model for VERITY Case Processing Pipeline."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.case_processing.models import StageExecutionRecord
from backend.reconciliation.result import ReconciliationResult
from backend.reporting.models import FinancialTruthReport


class CaseProcessingResult(BaseModel):
    """The unified final output produced by the VERITY Finance Controller Pipeline."""
    case_id: str = Field(..., description="Unique case identifier")
    status: str = Field(..., description="Synthesized financial status (CONFIRMED, PARTIALLY_SETTLED, etc.)")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score (0.0 to 1.0)")
    
    # Authoritative Reconciliation & Report
    reconciliation: Optional[ReconciliationResult] = Field(default=None, description="Reconciliation output")
    report: Optional[FinancialTruthReport] = Field(default=None, description="Explainable truth report")
    
    # Financial Accounting Summary
    financial_summary: Dict[str, Any] = Field(default_factory=dict, description="Monetary summary metrics")
    
    # Diagnostics & Telemetry
    stage_records: List[StageExecutionRecord] = Field(default_factory=list, description="Stage telemetry")
    total_execution_time_ms: float = Field(default=0.0, description="End-to-end execution latency in ms")
    provenance_node_count: int = Field(default=0, description="Total nodes registered in Provenance DAG")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings")
    errors: List[str] = Field(default_factory=list, description="Execution errors")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic properties")

    def to_text_report(self) -> str:
        """Returns human-readable text representation of the financial truth report."""
        if self.report:
            return self.report.to_text_report()
        return f"Case: {self.case_id} | Status: {self.status} | Confidence: {int(self.confidence_score * 100)}%"

    def to_json(self, indent: int = 2) -> str:
        """Returns formatted JSON serialization."""
        return self.model_dump_json(indent=indent)
