"""Unit tests for EntityRegistry and EntityResolutionService end-to-end integration."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.entity import Entity, EntityType
from backend.entity_resolution.registry import EntityRegistry
from backend.entity_resolution.result import EntityResolutionStatus
from backend.entity_resolution.service import EntityResolutionService


@pytest.fixture
def entity_registry() -> EntityRegistry:
    e1 = Entity(
        id="ENT-BHARAT-TECH",
        canonical_name="Bharat Tech Solutions Pvt Ltd",
        entity_type=EntityType.PRIVATE_LIMITED,
        gstin="29ABCDE1234F1Z5",
        pan="ABCDE1234F",
        upi_ids=["bharattech@okhdfcbank", "bharattech@icici"],
        phone_numbers=["+919876543210"],
        aliases=["Bharat Tech", "Bharat Technologies"],
    )
    e2 = Entity(
        id="ENT-PRIYA",
        canonical_name="Priya Patel",
        entity_type=EntityType.FREELANCER,
        pan="PXYZP1234K",
        upi_ids=["priyapatel@ybl"],
        phone_numbers=["+919811223344"],
        aliases=["Priya P"],
    )
    return EntityRegistry([e1, e2])


def test_registry_indexing_and_lookups(entity_registry: EntityRegistry) -> None:
    # Tax ID lookup
    assert entity_registry.find_by_tax_id("29ABCDE1234F1Z5").id == "ENT-BHARAT-TECH"
    assert entity_registry.find_by_tax_id("PXYZP1234K").id == "ENT-PRIYA"

    # UPI lookup
    assert entity_registry.find_by_upi_vpa("bharattech@okhdfcbank").id == "ENT-BHARAT-TECH"
    assert entity_registry.find_by_upi_vpa("priyapatel@ybl").id == "ENT-PRIYA"

    # Phone lookup
    assert entity_registry.find_by_phone("9876543210").id == "ENT-BHARAT-TECH"
    assert entity_registry.find_by_phone("+91-9811223344").id == "ENT-PRIYA"


def test_service_resolve_claim(entity_registry: EntityRegistry) -> None:
    service = EntityResolutionService(registry=entity_registry)

    # Claim with UPI VPA in counterparty hint
    claim_upi = Claim(
        id="CLM-UPI-001",
        evidence_id="EVID-001",
        claim_type=ClaimType.PAYMENT_RECEIVED,
        claimed_amount=15000.0,
        counterparty_hint="priyapatel@ybl",
    )
    res_upi = service.resolve_claim(claim_upi)
    assert res_upi.status == EntityResolutionStatus.CONFIRMED
    assert res_upi.selected_entity_id == "ENT-PRIYA"
    assert res_upi.claim_id == "CLM-UPI-001"

    # Claim with trade alias
    claim_alias = Claim(
        id="CLM-ALIAS-001",
        evidence_id="EVID-002",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=48000.0,
        counterparty_hint="Bharat Tech",
    )
    res_alias = service.resolve_claim(claim_alias)
    assert res_alias.status == EntityResolutionStatus.CONFIRMED
    assert res_alias.selected_entity_id == "ENT-BHARAT-TECH"


def test_service_resolve_claims_batch(entity_registry: EntityRegistry) -> None:
    service = EntityResolutionService(registry=entity_registry)
    claims = [
        Claim(id="C1", evidence_id="E1", claim_type=ClaimType.PAYMENT_RECEIVED, counterparty_hint="priyapatel@ybl"),
        Claim(id="C2", evidence_id="E2", claim_type=ClaimType.PAYMENT_RECEIVED, counterparty_hint="Bharat Tech"),
        Claim(id="C3", evidence_id="E3", claim_type=ClaimType.PAYMENT_RECEIVED, counterparty_hint=None),
    ]

    results = service.resolve_claims_batch(claims)
    assert len(results) == 3
    assert results[0].status == EntityResolutionStatus.CONFIRMED
    assert results[1].status == EntityResolutionStatus.CONFIRMED
    assert results[2].status == EntityResolutionStatus.UNRESOLVED


def test_service_backward_compatibility_base_resolver(entity_registry: EntityRegistry) -> None:
    service = EntityResolutionService(registry=entity_registry)
    res = service.resolve_entity(query_name="Bharat Tech")
    assert res is not None
    ent, score = res
    assert ent.id == "ENT-BHARAT-TECH"
    assert score >= 0.90
