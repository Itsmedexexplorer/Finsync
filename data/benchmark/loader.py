"""Loader and schema validation for the VERITY Ground-Truth Benchmark dataset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.claim import Claim, ClaimType
from backend.domain.entity import Entity
from backend.domain.transaction import Transaction, TransactionDirection, PaymentMethod
from backend.domain.reconciliation import MatchType, ReconciliationStatus
from backend.domain.discrepancy import DiscrepancyType


class GroundTruthExpectation(BaseModel):
    """Ground truth expectations for a benchmark case."""
    expected_status: ReconciliationStatus
    expected_match_type: MatchType
    expected_reconciled_amount: float
    expected_outstanding_amount: float
    expected_discrepancies: List[str] = Field(default_factory=list)
    confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    resolution_notes: str


class BenchmarkCase(BaseModel):
    """A complete self-contained test case in the VERITY ground-truth benchmark."""
    case_id: str
    category: str
    scenario_title: str
    description: str
    language: str = "en"
    entity: Optional[Entity] = None
    evidence: List[Evidence] = Field(default_factory=list)
    claims: List[Claim] = Field(default_factory=list)
    transactions: List[Transaction] = Field(default_factory=list)
    ground_truth: GroundTruthExpectation


def load_benchmark_cases(
    file_path: Optional[Path] = None,
    category_filter: Optional[str] = None,
) -> List[BenchmarkCase]:
    """Load and validate benchmark cases from JSON dataset."""
    if file_path is None:
        # Default to standard location
        file_path = Path(__file__).parent / "ground_truth_cases.json"
    
    if not file_path.exists():
        raise FileNotFoundError(f"Benchmark file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    cases: List[BenchmarkCase] = []
    for item in raw_data:
        if category_filter and item.get("category") != category_filter:
            continue
        case = BenchmarkCase.model_validate(item)
        cases.append(case)

    return cases
