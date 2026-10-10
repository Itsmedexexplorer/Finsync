"""Unit tests for Ambiguity Preservation and Conflict Detection in Entity Resolution."""

import pytest
from backend.domain.entity import Entity, EntityType
from backend.entity_resolution.matcher import EntityMatcher
from backend.entity_resolution.registry import EntityRegistry
from backend.entity_resolution.result import EntityResolutionStatus
from backend.entity_resolution.service import EntityResolutionService


@pytest.fixture
def entity_service() -> EntityResolutionService:
    ent1 = Entity(
        id="ENT-A",
        canonical_name="Rahul Kumar",
        entity_type=EntityType.INDIVIDUAL,
        upi_ids=["rahulkumar@ybl"],
        phone_numbers=["+919876543210"],
        aliases=["Rahul K"],
    )
    ent2 = Entity(
        id="ENT-B",
        canonical_name="Rahul Sharma",
        entity_type=EntityType.INDIVIDUAL,
        upi_ids=["rahul.sharma@okhdfcbank"],
        phone_numbers=["+919811022334"],
        aliases=["Rahul S"],
    )
    ent3 = Entity(
        id="ENT-C",
        canonical_name="Rohit Kumar",
        entity_type=EntityType.INDIVIDUAL,
        upi_ids=["rohit.k@icici"],
        phone_numbers=["+919988776655"],
        aliases=["Rohit K"],
    )
    registry = EntityRegistry([ent1, ent2, ent3])
    return EntityResolutionService(registry=registry)


def test_ambiguity_preserved_for_common_first_name(entity_service: EntityResolutionService) -> None:
    """When query 'Rahul' matches Rahul Kumar and Rahul Sharma without extra identifiers -> AMBIGUOUS."""
    result = entity_service.resolve_query(query_name="Rahul")
    
    assert result.status == EntityResolutionStatus.AMBIGUOUS
    assert result.selected_entity_id is None  # CRITICAL: Never guess!
    assert len(result.candidates) >= 2
    assert "Ambiguous identity" in result.explanation


def test_ambiguity_preserved_for_ambiguous_initials(entity_service: EntityResolutionService) -> None:
    """When query 'R. Kumar' matches both Rahul Kumar and Rohit Kumar -> AMBIGUOUS."""
    result = entity_service.resolve_query(query_name="R. Kumar")
    
    assert result.status == EntityResolutionStatus.AMBIGUOUS
    assert result.selected_entity_id is None


def test_conflict_detection_matching_phone_conflicting_vpa(entity_service: EntityResolutionService) -> None:
    """When phone matches Rahul Kumar (ENT-A), but UPI VPA belongs to a different handle -> CONFLICTING."""
    result = entity_service.resolve_query(
        query_name="Rahul Kumar",
        query_phone="9876543210",
        query_handle="totally_unrelated_vpa@paytm",
    )
    
    assert result.status == EntityResolutionStatus.CONFLICTING
    assert result.selected_entity_id is None
    assert "CONFLICTING_UPI_VPA" in result.conflicting_signals


def test_unresolved_when_no_identity_parameters_provided(entity_service: EntityResolutionService) -> None:
    """When no identity parameters exist (e.g. 'Payment received ₹15,000') -> UNRESOLVED."""
    result = entity_service.resolve_query()
    
    assert result.status == EntityResolutionStatus.UNRESOLVED
    assert result.selected_entity_id is None
    assert result.score == 0.0
