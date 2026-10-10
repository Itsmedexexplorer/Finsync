"""Unit tests for Cross-Case domain models (Day 18)."""

import pytest
from backend.cross_case.models import (
    CaseIntelligenceProfile,
    CorrelationRelationshipType,
    CounterpartyHistory,
    CrossCaseCorrelation,
    HistoricalRiskSignal,
    RecurringDiscrepancyPattern,
    ReferenceCorrelation,
)


def test_counterparty_history_model_defaults():
    history = CounterpartyHistory(
        entity_id="ENT-001",
        canonical_name="Acme Corp",
    )
    assert history.entity_id == "ENT-001"
    assert history.canonical_name == "Acme Corp"
    assert history.case_count == 0
    assert history.total_exposure == 0.0
    assert history.aliases == []
    assert history.historical_risk_signals == []


def test_reference_correlation_model():
    ref = ReferenceCorrelation(
        reference_id="UTR408219381920",
        previous_case_ids=["CASE-1", "CASE-2"],
        occurrence_count=2,
        reuse_warning=True,
    )
    assert ref.reference_id == "UTR408219381920"
    assert ref.reuse_warning is True
    assert len(ref.previous_case_ids) == 2


def test_recurring_discrepancy_pattern_model():
    pat = RecurringDiscrepancyPattern(
        entity_name="Creative Minds",
        discrepancy_type="AMOUNT_MISMATCH",
        occurrence_count=3,
        affected_case_ids=["CASE-A", "CASE-B", "CASE-C"],
        total_affected_exposure=75000.0,
    )
    assert pat.occurrence_count == 3
    assert pat.total_affected_exposure == 75000.0


def test_cross_case_correlation_model():
    corr = CrossCaseCorrelation(
        current_case_id="CASE-CURRENT",
        related_case_id="CASE-PAST",
        relationship_type=CorrelationRelationshipType.SHARED_REFERENCE,
        shared_identifier="UTR-12345",
        deterministic_reason="Identical bank reference / UTR: 'UTR-12345'",
        supporting_ids=["TXN-1", "TXN-2"],
    )
    assert corr.current_case_id == "CASE-CURRENT"
    assert corr.related_case_id == "CASE-PAST"
    assert corr.relationship_type == CorrelationRelationshipType.SHARED_REFERENCE


def test_case_intelligence_profile_assembly():
    profile = CaseIntelligenceProfile(
        case_id="CASE-100",
        counterparty_histories=[],
        reference_correlations=[],
        recurring_discrepancies=[],
        related_cases=[],
        historical_risk_signals=[],
    )
    assert profile.case_id == "CASE-100"
    dump = profile.model_dump()
    assert dump["case_id"] == "CASE-100"
