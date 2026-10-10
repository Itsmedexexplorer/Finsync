"""Unit tests for EntityMatcher multi-signal scoring and explainability."""

import pytest
from backend.domain.entity import Entity, EntityType
from backend.entity_resolution.matcher import EntityMatcher
from backend.entity_resolution.result import EntityResolutionStatus


@pytest.fixture
def sample_entity() -> Entity:
    return Entity(
        id="ENT-TEST-001",
        canonical_name="Ramesh Sharma",
        entity_type=EntityType.INDIVIDUAL,
        gstin="27ABCDE1234F1Z5",
        pan="ABCDE1234F",
        upi_ids=["ramesh@okhdfcbank"],
        phone_numbers=["+919876543210"],
        aliases=["Ramesh Trading Co", "R. Sharma"],
    )


def test_matcher_exact_gstin_and_pan(sample_entity: Entity) -> None:
    # GSTIN match
    cand_gst = EntityMatcher.evaluate_candidate(sample_entity, query_tax_id="27ABCDE1234F1Z5")
    assert cand_gst.score == 1.0
    assert "EXACT_TAX_ID" in cand_gst.matched_signals
    assert len(cand_gst.conflicting_signals) == 0

    # PAN match
    cand_pan = EntityMatcher.evaluate_candidate(sample_entity, query_tax_id="ABCDE1234F")
    assert cand_pan.score == 1.0
    assert "EXACT_TAX_ID" in cand_pan.matched_signals


def test_matcher_exact_upi_vpa(sample_entity: Entity) -> None:
    cand = EntityMatcher.evaluate_candidate(sample_entity, query_handle="ramesh@okhdfcbank")
    assert cand.score >= 0.98
    assert "EXACT_UPI_VPA" in cand.matched_signals
    assert "UPI VPA" in cand.explanation


def test_matcher_exact_phone(sample_entity: Entity) -> None:
    cand = EntityMatcher.evaluate_candidate(sample_entity, query_phone="9876543210")
    assert cand.score >= 0.95
    assert "EXACT_PHONE" in cand.matched_signals


def test_matcher_canonical_name_and_alias(sample_entity: Entity) -> None:
    # Exact canonical name
    cand_name = EntityMatcher.evaluate_candidate(sample_entity, query_name="Ramesh Sharma")
    assert cand_name.score >= 0.95
    assert "EXACT_CANONICAL_NAME" in cand_name.matched_signals

    # Registered alias
    cand_alias = EntityMatcher.evaluate_candidate(sample_entity, query_name="Ramesh Trading Co")
    assert cand_alias.score >= 0.92
    assert "EXACT_ALIAS" in cand_alias.matched_signals


def test_matcher_initials_variation(sample_entity: Entity) -> None:
    cand = EntityMatcher.evaluate_candidate(sample_entity, query_name="R. Sharma")
    assert cand.score >= 0.65
    assert "INITIALS_MATCH" in cand.matched_signals or "EXACT_ALIAS" in cand.matched_signals


def test_matcher_scoring_explainability(sample_entity: Entity) -> None:
    cand = EntityMatcher.evaluate_candidate(
        sample_entity,
        query_name="Ramesh Sharma",
        query_handle="ramesh@okhdfcbank",
        query_phone="9876543210",
    )
    # Reinforced multi-signal score
    assert cand.score >= 0.98
    assert "EXACT_CANONICAL_NAME" in cand.matched_signals
    assert "EXACT_UPI_VPA" in cand.matched_signals
    assert "EXACT_PHONE" in cand.matched_signals
    assert len(cand.explanation) > 10
