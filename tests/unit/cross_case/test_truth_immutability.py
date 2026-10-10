"""Unit tests proving Deterministic Truth Immutability under Historical Intelligence (Day 18).

Invariant:
Historical intelligence (prior contradictions, recurring discrepancies, reference reuse)
MUST NEVER alter reconciliation status, matched amount, or ledger integrity of a newly processed case.
"""

import os
import tempfile
import pytest

from backend.case_processing.service import CaseProcessingService
from backend.cross_case.service import CrossCaseIntelligenceService
from backend.storage.config import StorageSettings
from backend.storage.database import DatabaseEngine
from backend.storage.service import StorageService


@pytest.fixture
def memory_pipeline():
    temp_dir = tempfile.mkdtemp(prefix="verity_test_truth_")
    db_path = os.path.join(temp_dir, "test_truth.db")
    settings = StorageSettings(database_url=f"sqlite:///{db_path}", pool_size=3)
    engine = DatabaseEngine(settings=settings)
    engine.initialize()

    case_service = CaseProcessingService()
    storage_service = StorageService(engine=engine)
    cross_service = CrossCaseIntelligenceService(engine=engine)

    yield case_service, storage_service, cross_service
    engine.shutdown()


def test_truth_immutability_under_bad_counterparty_history(memory_pipeline):
    case_service, storage_service, cross_service = memory_pipeline

    # 1. Historical Case 1: Bad Vendor has severe contradiction
    case_hist = {
        "case_id": "CASE-BAD-01",
        "evidence": [
            {
                "id": "EV-H1",
                "modality": "INVOICE",
                "source_name": "inv_1.txt",
                "source_type": "MANUAL_UPLOAD",
                "raw_payload": "INVOICE #DC-401 Vendor: Shady Supplies Amount: INR 50,000",
            },
            {
                "id": "EV-H2",
                "modality": "MESSAGING_CHAT",
                "source_name": "WhatsApp_Chat.txt",
                "source_type": "WHATSAPP_EXPORT",
                "raw_payload": "Vendor claims only INR 30,000 was approved for Invoice DC-401.",
            }
        ],
        "claims": [
            {
                "id": "CLM-H1",
                "evidence_id": "EV-H1",
                "claim_type": "INVOICE_ISSUED",
                "claimed_amount": 50000.0,
                "reference_id_hint": "INV-DC-401",
                "counterparty_hint": "Shady Supplies",
            },
            {
                "id": "CLM-H2",
                "evidence_id": "EV-H2",
                "claim_type": "PAYMENT_SENT",
                "claimed_amount": 30000.0,
                "reference_id_hint": "INV-DC-401",
                "counterparty_hint": "Shady Supplies",
            }
        ],
        "transactions": [],
        "entities": [{"id": "ENT-SS1", "canonical_name": "Shady Supplies"}],
    }
    res_hist = case_service.process_benchmark_case(case_hist)
    storage_service.process_and_persist_case(
        case_result=res_hist,
        raw_evidence_list=case_hist["evidence"],
        raw_claims_list=case_hist["claims"],
        raw_entities_list=case_hist["entities"],
        raw_transactions_list=case_hist["transactions"],
    )
    assert res_hist.status == "CONTRADICTED"

    # 2. Current Case 2: Clean 1:1 settlement with Shady Supplies for ₹20,000
    case_curr = {
        "case_id": "CASE-CLEAN-02",
        "evidence": [
            {
                "id": "EV-C1",
                "modality": "INVOICE",
                "source_name": "inv_clean.txt",
                "source_type": "MANUAL_UPLOAD",
                "raw_payload": "INVOICE #C-2 Vendor: Shady Supplies Amount: INR 20,000",
            },
            {
                "id": "EV-C2",
                "modality": "BANK_STATEMENT",
                "source_name": "bank_c.csv",
                "source_type": "BANK_CSV",
                "raw_payload": "Credit 20000 UTR-CLEAN-222",
            }
        ],
        "claims": [
            {
                "id": "CLM-C1",
                "evidence_id": "EV-C1",
                "claim_type": "INVOICE_ISSUED",
                "claimed_amount": 20000.0,
                "reference_id_hint": "UTR-CLEAN-222",
                "counterparty_hint": "Shady Supplies",
            }
        ],
        "transactions": [
            {
                "id": "TXN-C1",
                "amount": 20000.0,
                "direction": "CREDIT",
                "bank_reference": "UTR-CLEAN-222",
                "evidence_ids": ["EV-C2"],
            }
        ],
        "entities": [{"id": "ENT-SS2", "canonical_name": "Shady Supplies"}],
    }
    res_curr = case_service.process_benchmark_case(case_curr)
    storage_service.process_and_persist_case(
        case_result=res_curr,
        raw_evidence_list=case_curr["evidence"],
        raw_claims_list=case_curr["claims"],
        raw_entities_list=case_curr["entities"],
        raw_transactions_list=case_curr["transactions"],
    )

    # STRICT INVARIANT: Status MUST be CONFIRMED based strictly on current objective evidence
    assert res_curr.status == "CONFIRMED"
    assert res_curr.reconciliation.matched_amount == 20000.0
    assert res_curr.reconciliation.outstanding_amount == 0.0

    # Cross-case intelligence surfaces historical risk for the human operator/controller without mutating truth
    profile = cross_service.build_case_intelligence_profile("CASE-CLEAN-02")
    assert len(profile.counterparty_histories) == 1
    assert profile.counterparty_histories[0].contradiction_count == 1
    assert profile.counterparty_histories[0].disputed_exposure == 80000.0

    # Risk signals alert operator to past contradiction
    sig_types = {s.signal_type for s in profile.historical_risk_signals}
    assert "REPEAT_CONTRADICTION" in sig_types
