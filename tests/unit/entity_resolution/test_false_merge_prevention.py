"""Unit tests verifying strict prevention of false merges."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.entity import Entity, EntityType
from backend.entity_resolution.matcher import EntityMatcher
from backend.entity_resolution.registry import EntityRegistry
from backend.entity_resolution.result import EntityResolutionStatus
from backend.entity_resolution.service import EntityResolutionService


@pytest.fixture
def populated_service() -> EntityResolutionService:
    ent1 = Entity(
        id="ENT-RAHUL-KUMAR",
        canonical_name="Rahul Kumar",
        entity_type=EntityType.INDIVIDUAL,
        upi_ids=["rahulkumar@ybl"],
        phone_numbers=["+919876543210"],
    )
    ent2 = Entity(
        id="ENT-ROHIT-KUMAR",
        canonical_name="Rohit Kumar",
        entity_type=EntityType.INDIVIDUAL,
        upi_ids=["rohitkumar@icici"],
        phone_numbers=["+919988776655"],
    )
    ent3 = Entity(
        id="ENT-RAHUL-SHARMA",
        canonical_name="Rahul Sharma",
        entity_type=EntityType.INDIVIDUAL,
        upi_ids=["rahul.sharma@okhdfcbank"],
        phone_numbers=["+919811022334"],
    )
    return EntityResolutionService(registry=EntityRegistry([ent1, ent2, ent3]))


def test_false_merge_prevented_between_similar_names(populated_service: EntityResolutionService) -> None:
    """'Rahul Kumar' and 'Rohit Kumar' must resolve to their own respective entities and never merge."""
    res_rahul = populated_service.resolve_query(query_name="Rahul Kumar")
    assert res_rahul.status == EntityResolutionStatus.CONFIRMED
    assert res_rahul.selected_entity_id == "ENT-RAHUL-KUMAR"

    res_rohit = populated_service.resolve_query(query_name="Rohit Kumar")
    assert res_rohit.status == EntityResolutionStatus.CONFIRMED
    assert res_rohit.selected_entity_id == "ENT-ROHIT-KUMAR"

    assert res_rahul.selected_entity_id != res_rohit.selected_entity_id


def test_false_merge_prevented_by_transaction_amount_invariance(populated_service: EntityResolutionService) -> None:
    """Core financial rule: Two claims having the exact same amount & date (₹20,000 on 2026-08-15)
    must NOT cause different entities to merge or resolve incorrectly."""
    claim1 = Claim(
        id="CLM-001",
        evidence_id="EVID-001",
        claim_type=ClaimType.PAYMENT_RECEIVED,
        claimed_amount=20000.0,
        claimed_date="2026-08-15",
        counterparty_hint="Rahul Kumar",
    )
    claim2 = Claim(
        id="CLM-002",
        evidence_id="EVID-002",
        claim_type=ClaimType.PAYMENT_RECEIVED,
        claimed_amount=20000.0,
        claimed_date="2026-08-15",
        counterparty_hint="Rahul Sharma",
    )

    res1 = populated_service.resolve_claim(claim1)
    res2 = populated_service.resolve_claim(claim2)

    assert res1.selected_entity_id == "ENT-RAHUL-KUMAR"
    assert res2.selected_entity_id == "ENT-RAHUL-SHARMA"
    assert res1.selected_entity_id != res2.selected_entity_id


def test_false_merge_prevented_when_first_name_same_last_name_differs(populated_service: EntityResolutionService) -> None:
    """A claim for 'Rahul Gupta' (unregistered) against known 'Rahul Kumar' and 'Rahul Sharma'
    must NOT merge into either of them."""
    res = populated_service.resolve_query(query_name="Rahul Gupta")
    
    # Must NOT merge into Rahul Kumar or Rahul Sharma
    assert res.selected_entity_id is None
    assert res.status in (EntityResolutionStatus.UNRESOLVED, EntityResolutionStatus.AMBIGUOUS, EntityResolutionStatus.CONFLICTING)
