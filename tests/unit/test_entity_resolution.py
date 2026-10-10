"""Unit tests for Entity Resolution and identifier matching."""

import pytest
from backend.domain.entity import Entity, EntityType
from backend.entity_resolution.base import DeterministicEntityResolver


@pytest.fixture
def entity_resolver() -> DeterministicEntityResolver:
    resolver = DeterministicEntityResolver()
    
    # Entity 1: Business with GSTIN, PAN, and Trade Aliases
    resolver.add_entity(Entity(
        id="ENT-001",
        canonical_name="Ramesh Enterprises Pvt Ltd",
        entity_type=EntityType.PRIVATE_LIMITED,
        gstin="29ABCDE1234F1Z5",
        pan="ABCDE1234F",
        upi_ids=["ramesh.ent@icici", "9811012345@paytm"],
        phone_numbers=["+919811012345"],
        aliases=["M/s Ramesh Enterprises", "Ramesh Ent", "RAMESH PVT LTD"],
    ))

    # Entity 2: Freelancer with UPI and Phone
    resolver.add_entity(Entity(
        id="ENT-002",
        canonical_name="Pooja Deshmukh",
        entity_type=EntityType.FREELANCER,
        upi_ids=["pooja_designs@okhdfcbank"],
        phone_numbers=["+919988776655"],
        aliases=["Pooja D", "Pooja Designs"],
    ))

    return resolver


def test_resolve_by_gstin_and_pan(entity_resolver: DeterministicEntityResolver) -> None:
    # GSTIN exact match
    res_gst = entity_resolver.resolve_entity(query_tax_id="29ABCDE1234F1Z5")
    assert res_gst is not None
    ent, conf = res_gst
    assert ent.id == "ENT-001"
    assert conf == 1.0

    # PAN exact match
    res_pan = entity_resolver.resolve_entity(query_tax_id="ABCDE1234F")
    assert res_pan is not None
    ent, conf = res_pan
    assert ent.id == "ENT-001"
    assert conf == 1.0


def test_resolve_by_upi_handle(entity_resolver: DeterministicEntityResolver) -> None:
    res = entity_resolver.resolve_entity(query_handle="pooja_designs@okhdfcbank")
    assert res is not None
    ent, conf = res
    assert ent.id == "ENT-002"
    assert conf >= 0.95


def test_resolve_by_phone_variations(entity_resolver: DeterministicEntityResolver) -> None:
    # Match with national number format
    res = entity_resolver.resolve_entity(query_phone="9811012345")
    assert res is not None
    ent, conf = res
    assert ent.id == "ENT-001"

    # Match with country code and formatting
    res2 = entity_resolver.resolve_entity(query_phone="+91-99887-76655")
    assert res2 is not None
    ent2, conf2 = res2
    assert ent2.id == "ENT-002"


def test_resolve_by_alias_and_tokens(entity_resolver: DeterministicEntityResolver) -> None:
    # Alias match
    res = entity_resolver.resolve_entity(query_name="M/s Ramesh Enterprises")
    assert res is not None
    ent, conf = res
    assert ent.id == "ENT-001"

    # Freelancer alias
    res2 = entity_resolver.resolve_entity(query_name="Pooja Designs")
    assert res2 is not None
    ent2, conf2 = res2
    assert ent2.id == "ENT-002"
