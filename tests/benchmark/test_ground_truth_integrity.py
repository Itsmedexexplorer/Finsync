"""Automated tests validating the integrity of the 75-100 case Ground-Truth Benchmark."""

from typing import List
import pytest
from backend.domain.reconciliation import ReconciliationStatus, MatchType
from data.benchmark.loader import BenchmarkCase, load_benchmark_cases


def test_benchmark_case_count(benchmark_cases: List[BenchmarkCase]) -> None:
    """Validate benchmark contains between 75 and 100 realistic cases."""
    assert 75 <= len(benchmark_cases) <= 100, f"Expected 75-100 cases, got {len(benchmark_cases)}"


def test_benchmark_all_required_categories_present(benchmark_cases: List[BenchmarkCase]) -> None:
    """Validate all 12 required scenario categories are represented."""
    required_categories = {
        "CLEAN_1TO1",
        "ONE_TO_MANY",
        "MANY_TO_ONE",
        "PARTIAL_PAYMENTS",
        "CROSS_MODAL_DUPLICATES",
        "CONTRADICTORY_CLAIMS",
        "MISSING_EVIDENCE",
        "IDENTITY_NAME_VARIATIONS",
        "INCORRECT_REF_IDS",
        "CASH_PAYMENT_CLAIMS",
        "MULTILINGUAL_HINGLISH",
        "AMBIGUOUS_CASES",
    }
    present_categories = {case.category for case in benchmark_cases}
    missing = required_categories - present_categories
    assert not missing, f"Missing required benchmark categories: {missing}"


def test_benchmark_case_ids_unique(benchmark_cases: List[BenchmarkCase]) -> None:
    """Validate every benchmark case has a unique case_id."""
    case_ids = [c.case_id for c in benchmark_cases]
    assert len(case_ids) == len(set(case_ids)), "Duplicate case_id found in benchmark"


def test_benchmark_amounts_and_statuses_valid(benchmark_cases: List[BenchmarkCase]) -> None:
    """Validate ground truth financial amounts and statuses for each benchmark case."""
    valid_statuses = {s.value for s in ReconciliationStatus}
    
    for case in benchmark_cases:
        gt = case.ground_truth
        assert gt.expected_status.value in valid_statuses
        assert gt.expected_reconciled_amount >= 0.0, f"Negative reconciled amount in {case.case_id}"
        assert gt.expected_outstanding_amount >= 0.0, f"Negative outstanding amount in {case.case_id}"
        assert 0.0 <= gt.confidence_threshold <= 1.0, f"Invalid confidence threshold in {case.case_id}"
        assert len(gt.resolution_notes.strip()) > 0, f"Empty resolution notes in {case.case_id}"

        # Intra-case evidence and claim validation
        for ev in case.evidence:
            assert ev.id, f"Missing evidence ID in {case.case_id}"
            assert ev.raw_payload, f"Empty raw payload in {ev.id} in {case.case_id}"
            assert len(ev.content_hash) == 64, f"Invalid SHA-256 hash in {ev.id}"

        for clm in case.claims:
            assert clm.id, f"Missing claim ID in {case.case_id}"
            assert clm.claimed_amount >= 0.0, f"Negative claim amount in {clm.id}"
            # Claim's evidence_id must point to an evidence item in the case
            ev_ids = {e.id for e in case.evidence}
            assert clm.evidence_id in ev_ids, f"Claim {clm.id} references non-existent evidence {clm.evidence_id}"

        for txn in case.transactions:
            assert txn.id, f"Missing txn ID in {case.case_id}"
            assert txn.amount > 0.0, f"Non-positive transaction amount in {txn.id}"


def test_expected_status_coverage(benchmark_cases: List[BenchmarkCase]) -> None:
    """Validate that all major expected statuses are covered."""
    statuses = {case.ground_truth.expected_status for case in benchmark_cases}
    assert ReconciliationStatus.CONFIRMED in statuses
    assert ReconciliationStatus.PARTIAL in statuses
    assert ReconciliationStatus.DUPLICATE in statuses
    assert ReconciliationStatus.CONTRADICTED in statuses
    assert ReconciliationStatus.UNVERIFIABLE in statuses
    assert ReconciliationStatus.AMBIGUOUS in statuses
