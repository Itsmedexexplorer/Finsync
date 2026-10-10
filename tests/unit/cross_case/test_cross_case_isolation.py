"""Unit tests proving Cross-Case Isolation and zero state leakage (Day 18)."""

import os
import tempfile
import pytest

from backend.case_processing.service import CaseProcessingService
from backend.cross_case.service import CrossCaseIntelligenceService
from backend.storage.config import StorageSettings
from backend.storage.database import DatabaseEngine
from backend.storage.service import StorageService


@pytest.fixture
def isolated_setup():
    temp_dir = tempfile.mkdtemp(prefix="verity_test_iso_")
    db_path = os.path.join(temp_dir, "test_iso.db")
    settings = StorageSettings(database_url=f"sqlite:///{db_path}", pool_size=3)
    engine = DatabaseEngine(settings=settings)
    engine.initialize()

    case_service = CaseProcessingService()
    storage_service = StorageService(engine=engine)
    cross_service = CrossCaseIntelligenceService(engine=engine)

    yield case_service, storage_service, cross_service
    engine.shutdown()


def test_cross_case_isolation_no_leakage(isolated_setup):
    case_service, storage_service, cross_service = isolated_setup

    # 1. Process Case A (Dispute / Contradicted)
    case_a = {
        "case_id": "CASE-ISO-A",
        "evidence": [
            {
                "id": "EV-A-1",
                "modality": "INVOICE",
                "source_name": "inv_a.txt",
                "source_type": "MANUAL_UPLOAD",
                "raw_payload": "INVOICE #A-101 Vendor: Vendor Alpha Amount: INR 50,000",
            },
            {
                "id": "EV-A-2",
                "modality": "MESSAGING_CHAT",
                "source_name": "chat_a.txt",
                "source_type": "WHATSAPP_EXPORT",
                "raw_payload": "Vendor claims only 25,000 was due",
            }
        ],
        "claims": [
            {
                "id": "CLM-A-1",
                "evidence_id": "EV-A-1",
                "claim_type": "INVOICE_ISSUED",
                "claimed_amount": 50000.0,
                "reference_id_hint": "INV-A-101",
                "counterparty_hint": "Vendor Alpha",
            },
            {
                "id": "CLM-A-2",
                "evidence_id": "EV-A-2",
                "claim_type": "PAYMENT_SENT",
                "claimed_amount": 25000.0,
                "reference_id_hint": "INV-A-101",
                "counterparty_hint": "Vendor Alpha",
            }
        ],
        "transactions": [],
        "entities": [
            {"id": "ENT-A", "canonical_name": "Vendor Alpha"}
        ],
    }
    res_a = case_service.process_benchmark_case(case_a)
    storage_service.process_and_persist_case(
        case_result=res_a,
        raw_evidence_list=case_a["evidence"],
        raw_claims_list=case_a["claims"],
        raw_entities_list=case_a["entities"],
    )
    assert res_a.status == "CONTRADICTED"

    # 2. Process Case B (Clean unrelated Vendor Beta)
    case_b = {
        "case_id": "CASE-ISO-B",
        "evidence": [
            {
                "id": "EV-B-1",
                "modality": "INVOICE",
                "source_name": "inv_b.txt",
                "source_type": "MANUAL_UPLOAD",
                "raw_payload": "INVOICE #B-201 Vendor: Vendor Beta Amount: INR 10,000",
            },
            {
                "id": "EV-B-2",
                "modality": "BANK_STATEMENT",
                "source_name": "bank_b.csv",
                "source_type": "BANK_CSV",
                "raw_payload": "Credit 10000 UTR-B-999",
            }
        ],
        "claims": [
            {
                "id": "CLM-B-1",
                "evidence_id": "EV-B-1",
                "claim_type": "INVOICE_ISSUED",
                "claimed_amount": 10000.0,
                "reference_id_hint": "UTR-B-999",
                "counterparty_hint": "Vendor Beta",
            }
        ],
        "transactions": [
            {
                "id": "TXN-B-1",
                "amount": 10000.0,
                "direction": "CREDIT",
                "bank_reference": "UTR-B-999",
                "evidence_ids": ["EV-B-2"],
            }
        ],
        "entities": [
            {"id": "ENT-B", "canonical_name": "Vendor Beta"}
        ],
    }
    res_b = case_service.process_benchmark_case(case_b)
    storage_service.process_and_persist_case(
        case_result=res_b,
        raw_evidence_list=case_b["evidence"],
        raw_claims_list=case_b["claims"],
        raw_entities_list=case_b["entities"],
        raw_transactions_list=case_b["transactions"],
    )

    # Invariant: Case B remains 100% CONFIRMED with zero contamination from Case A
    assert res_b.status == "CONFIRMED"
    assert res_b.reconciliation.matched_amount == 10000.0
    assert res_b.reconciliation.outstanding_amount == 0.0

    # Cross-case query on Case B finds 0 correlations with Case A
    corrs_b = cross_service.get_case_correlations("CASE-ISO-B")
    assert len(corrs_b) == 0
