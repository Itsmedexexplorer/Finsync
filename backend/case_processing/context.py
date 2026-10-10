"""Typed Context container tracking intermediate state across all pipeline stages."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.case_processing.models import CaseInput, StageExecutionRecord
from backend.contradiction_detection.result import ContradictionResult
from backend.deduplication.result import DeduplicationGroup, DeduplicationResult
from backend.domain.claim import Claim
from backend.domain.discrepancy import Discrepancy
from backend.domain.entity import Entity
from backend.domain.evidence import Evidence
from backend.domain.transaction import Transaction
from backend.reconciliation.result import BatchReconciliationResult, ReconciliationResult
from backend.reporting.models import FinancialTruthReport
from backend.transaction_matching.result import MatchRelationship, TransactionMatchingResult


class CaseProcessingContext(BaseModel):
    """Encapsulates all intermediate and final artifacts generated during pipeline execution."""
    case_id: str = Field(..., description="Unique case identifier")
    case_input: CaseInput = Field(..., description="Initial input payload")
    
    # Ingestion & Normalization
    evidence: List[Evidence] = Field(default_factory=list, description="All normalized Evidence objects")
    
    # Claim Extraction
    claims: List[Claim] = Field(default_factory=list, description="All extracted Claim objects")
    
    # Entity Resolution
    entities: List[Entity] = Field(default_factory=list, description="Known and resolved Entity objects")
    claim_entity_map: Dict[str, str] = Field(default_factory=dict, description="Map of claim_id -> entity_id")
    
    # Ledger Transactions
    transactions: List[Transaction] = Field(default_factory=list, description="Verified Transaction records")
    
    # Transaction Matching
    matching_result: Optional[TransactionMatchingResult] = Field(default=None, description="Day 5 matching result")
    match_relationships: List[MatchRelationship] = Field(default_factory=list, description="Topological match links")
    
    # Deduplication
    deduplication_result: Optional[DeduplicationResult] = Field(default=None, description="Day 6 deduplication result")
    deduplication_groups: List[DeduplicationGroup] = Field(default_factory=list, description="Canonical event groups")
    
    # Contradiction Detection
    contradiction_result: Optional[ContradictionResult] = Field(default=None, description="Day 7 contradiction result")
    discrepancies: List[Discrepancy] = Field(default_factory=list, description="Detected financial discrepancies")
    
    # Reconciliation
    reconciliation_result: Optional[BatchReconciliationResult] = Field(default=None, description="Day 8 batch reconciliation")
    primary_reconciliation: Optional[ReconciliationResult] = Field(default=None, description="Primary event reconciliation")
    
    # Reporting & Explainability
    reports: List[FinancialTruthReport] = Field(default_factory=list, description="Day 9 financial truth reports")
    primary_report: Optional[FinancialTruthReport] = Field(default=None, description="Primary case report")
    
    # Execution Tracking
    stage_records: List[StageExecutionRecord] = Field(default_factory=list, description="Per-stage diagnostic telemetry")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings encountered")
    errors: List[str] = Field(default_factory=list, description="Errors encountered during execution")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic properties")
