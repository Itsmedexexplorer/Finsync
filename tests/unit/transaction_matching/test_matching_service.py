"""Unit tests for TransactionMatchingService orchestrating matching and entity resolution."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.entity import Entity, EntityType
from backend.domain.reconciliation import MatchType
from backend.domain.transaction import Transaction, TransactionDirection
from backend.entity_resolution.registry import EntityRegistry
from backend.entity_resolution.service import EntityResolutionService
from backend.transaction_matching.result import MatchRelationshipType, MatchStatus
from backend.transaction_matching.service import TransactionMatchingService


@pytest.fixture
def matching_service_with_entities() -> TransactionMatchingService:
    ent1 = Entity(
        id="ENT-BHARAT-01",
        canonical_name="Bharat Tech Solutions Pvt Ltd",
        entity_type=EntityType.PRIVATE_LIMITED,
        upi_ids=["bharattech@okhdfcbank"],
        phone_numbers=["+919876543210"],
        aliases=["Bharat Tech"],
    )
    registry = EntityRegistry([ent1])
    entity_service = EntityResolutionService(registry=registry)
    return TransactionMatchingService(entity_service=entity_service)


def test_matching_service_dynamically_links_entity(matching_service_with_entities: TransactionMatchingService) -> None:
    claim = Claim(
        id="CLM-SVC-01",
        evidence_id="EVID-01",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=30000.0,
        claimed_date="2026-08-10",
        counterparty_hint="Bharat Tech",  # Dynamically resolved to ENT-BHARAT-01
    )
    txn = Transaction(
        id="TXN-SVC-01",
        amount=30000.0,
        direction=TransactionDirection.CREDIT,
        origin_entity_id="ENT-BHARAT-01",
        timestamp="2026-08-12T10:00:00Z",
    )

    result = matching_service_with_entities.match_records(claims=[claim], transactions=[txn])
    assert len(result.relationships) == 1
    rel = result.relationships[0]
    assert rel.relationship_type == MatchRelationshipType.ONE_TO_ONE
    assert rel.status == MatchStatus.MATCHED
    assert rel.entity_id == "ENT-BHARAT-01"


def test_matching_service_backward_compatibility(matching_service_with_entities: TransactionMatchingService) -> None:
    claim = Claim(
        id="CLM-BC-01",
        evidence_id="EVID-01",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=20000.0,
        reference_id_hint="408219381920",
    )
    txn = Transaction(
        id="TXN-BC-01",
        amount=20000.0,
        direction=TransactionDirection.CREDIT,
        bank_reference="408219381920",
    )

    candidates = matching_service_with_entities.match(claims=[claim], transactions=[txn])
    assert len(candidates) == 1
    assert candidates[0].match_type == MatchType.EXACT_1_TO_1
    assert candidates[0].confidence >= 0.90
