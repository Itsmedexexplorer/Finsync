"""Unit tests for Case Correlation & Relationship Discovery (Day 18)."""

import os
import tempfile
import pytest

from backend.cross_case.models import CorrelationRelationshipType
from backend.cross_case.service import CrossCaseIntelligenceService
from backend.storage.config import StorageSettings
from backend.storage.database import DatabaseEngine
from backend.storage.models import (
    CaseRecord,
    EntityRecord,
    EvidenceRecord,
    TransactionRecord,
)
from backend.storage.repositories.sql.case import SQLCaseRepository
from backend.storage.repositories.sql.entity import SQLEntityRepository
from backend.storage.repositories.sql.evidence import SQLEvidenceRepository
from backend.storage.repositories.sql.transaction import SQLTransactionRepository


@pytest.fixture
def test_engine():
    temp_dir = tempfile.mkdtemp(prefix="verity_test_corr_")
    db_path = os.path.join(temp_dir, "test_corr.db")
    settings = StorageSettings(database_url=f"sqlite:///{db_path}", pool_size=3)
    engine = DatabaseEngine(settings=settings)
    engine.initialize()
    yield engine
    engine.shutdown()


def test_shared_entity_and_reference_correlations(test_engine):
    service = CrossCaseIntelligenceService(engine=test_engine)

    with test_engine.transaction() as conn:
        case_repo = SQLCaseRepository(conn)
        ent_repo = SQLEntityRepository(conn)
        txn_repo = SQLTransactionRepository(conn)
        ev_repo = SQLEvidenceRepository(conn)

        # Historical Case
        case_repo.create(CaseRecord(case_id="HIST-101", status="CONFIRMED"))
        ent_repo.create(EntityRecord(
            id="ENT-H1",
            case_id="HIST-101",
            canonical_name="Starlight Media",
        ))
        txn_repo.create(TransactionRecord(
            id="TXN-H1",
            case_id="HIST-101",
            amount=40000.0,
            direction="CREDIT",
            bank_reference="UTR-STAR-101",
        ))
        ev_repo.create(EvidenceRecord(
            id="EV-H1",
            case_id="HIST-101",
            modality="INVOICE",
            sha256_hash="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        ))

        # Current Case
        case_repo.create(CaseRecord(case_id="CURR-202", status="CONFIRMED"))
        ent_repo.create(EntityRecord(
            id="ENT-C1",
            case_id="CURR-202",
            canonical_name="Starlight Media",
        ))
        txn_repo.create(TransactionRecord(
            id="TXN-C1",
            case_id="CURR-202",
            amount=40000.0,
            direction="CREDIT",
            bank_reference="UTR-STAR-101",
        ))
        ev_repo.create(EvidenceRecord(
            id="EV-C1",
            case_id="CURR-202",
            modality="INVOICE",
            sha256_hash="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        ))

    correlations = service.get_case_correlations("CURR-202")
    assert len(correlations) >= 3

    rel_types = {c.relationship_type for c in correlations}
    assert CorrelationRelationshipType.SHARED_ENTITY in rel_types
    assert CorrelationRelationshipType.SHARED_REFERENCE in rel_types
    assert CorrelationRelationshipType.SHARED_EVIDENCE_HASH in rel_types

    for c in correlations:
        assert c.current_case_id == "CURR-202"
        assert c.related_case_id == "HIST-101"
        assert len(c.supporting_ids) >= 2
        assert len(c.deterministic_reason) > 0
