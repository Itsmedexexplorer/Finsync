"""Unit tests for Case Processing API endpoints."""

import pytest
from fastapi.testclient import TestClient
from backend.api.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_submit_clean_case(client: TestClient) -> None:
    payload = {
        "case_id": "API-CASE-CLEAN-01",
        "evidence_items": [
            {
                "id": "E1",
                "modality": "INVOICE",
                "source_type": "ZOHO_INVOICE",
                "source_name": "inv.pdf",
                "raw_payload": "35k inv",
            }
        ],
        "transactions": [
            {
                "id": "T1",
                "amount": 35000.0,
                "direction": "CREDIT",
                "bank_reference": "408219381920",
                "origin_entity_id": "ENT-001",
            }
        ],
        "entities": [
            {
                "id": "ENT-001",
                "canonical_name": "Rahul Kumar",
                "entity_type": "INDIVIDUAL",
                "pan": "ABCDE1234F",
            }
        ],
        "metadata": {
            "precomputed_claims": [
                {
                    "id": "C1",
                    "evidence_id": "E1",
                    "claim_type": "INVOICE_ISSUED",
                    "claimed_amount": 35000.0,
                    "reference_id_hint": "408219381920",
                    "counterparty_hint": "Rahul Kumar",
                }
            ]
        },
    }

    response = client.post("/api/v1/cases", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["case_id"] == "API-CASE-CLEAN-01"
    assert data["status"] == "CONFIRMED"
    assert data["requires_review"] is False
    assert data["financial_summary"]["matched_amount"] == 35000.0


def test_submit_partial_case(client: TestClient) -> None:
    payload = {
        "case_id": "API-CASE-PART-01",
        "evidence_items": [
            {
                "id": "E-PART",
                "modality": "INVOICE",
                "source_type": "ZOHO_INVOICE",
                "source_name": "inv.pdf",
                "raw_payload": "20k inv",
            }
        ],
        "transactions": [
            {
                "id": "T-PART",
                "amount": 12000.0,
                "direction": "CREDIT",
                "origin_entity_id": "ENT-PRIYA",
            }
        ],
        "metadata": {
            "precomputed_claims": [
                {
                    "id": "C-PART",
                    "evidence_id": "E-PART",
                    "claim_type": "INVOICE_ISSUED",
                    "claimed_amount": 20000.0,
                    "counterparty_hint": "Priya Patel",
                }
            ],
            "claim_entity_map": {"C-PART": "ENT-PRIYA"},
            "precomputed_match_relationships": [
                {
                    "id": "MAT-02",
                    "relationship_type": "PARTIAL",
                    "status": "MATCHED",
                    "source_claim_ids": ["C-PART"],
                    "target_transaction_ids": ["T-PART"],
                    "matched_amount": 12000.0,
                    "target_amount": 20000.0,
                    "score": 0.95,
                    "explanation": "Partial payment",
                    "entity_id": "ENT-PRIYA",
                }
            ],
        },
    }

    response = client.post("/api/v1/cases", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("PARTIAL", "PARTIALLY_SETTLED")
    assert data["requires_review"] is True
    assert data["financial_summary"]["matched_amount"] == 12000.0
    assert data["financial_summary"]["outstanding_amount"] == 8000.0


def test_submit_contradicted_case(client: TestClient) -> None:
    payload = {
        "case_id": "API-CASE-CNF-01",
        "evidence_items": [
            {
                "id": "E-CNF",
                "modality": "INVOICE",
                "source_type": "ZOHO_INVOICE",
                "source_name": "inv.pdf",
                "raw_payload": "20k inv",
            }
        ],
        "transactions": [
            {
                "id": "T-CNF",
                "amount": 18000.0,
                "direction": "CREDIT",
                "bank_reference": "408219381920",
            }
        ],
        "metadata": {
            "precomputed_claims": [
                {
                    "id": "C-CNF",
                    "evidence_id": "E-CNF",
                    "claim_type": "INVOICE_ISSUED",
                    "claimed_amount": 20000.0,
                    "reference_id_hint": "408219381920",
                }
            ],
            "precomputed_discrepancies": [
                {
                    "id": "DISC-01",
                    "discrepancy_type": "AMOUNT_MISMATCH",
                    "severity": "ERROR",
                    "message": "Amount mismatch: 20k vs 18k",
                    "expected_value": "20000.00",
                    "observed_value": "18000.00",
                    "involved_claim_ids": ["C-CNF"],
                    "involved_transaction_ids": ["T-CNF"],
                }
            ],
        },
    }

    response = client.post("/api/v1/cases", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CONTRADICTED"
    assert data["requires_review"] is True


def test_submit_ambiguous_case(client: TestClient) -> None:
    payload = {
        "case_id": "API-CASE-AMB-01",
        "evidence_items": [
            {
                "id": "E-AMB",
                "modality": "INVOICE",
                "source_type": "ZOHO_INVOICE",
                "source_name": "inv.pdf",
                "raw_payload": "20k inv",
            }
        ],
        "transactions": [
            {"id": "T-AMB1", "amount": 20000.0, "direction": "CREDIT"},
            {"id": "T-AMB2", "amount": 20000.0, "direction": "CREDIT"},
        ],
        "metadata": {
            "precomputed_claims": [
                {
                    "id": "C-AMB",
                    "evidence_id": "E-AMB",
                    "claim_type": "INVOICE_ISSUED",
                    "claimed_amount": 20000.0,
                }
            ],
            "precomputed_match_relationships": [
                {
                    "id": "MAT-AMB",
                    "relationship_type": "ONE_TO_ONE",
                    "status": "AMBIGUOUS",
                    "source_claim_ids": ["C-AMB"],
                    "target_transaction_ids": ["T-AMB1", "T-AMB2"],
                    "matched_amount": 20000.0,
                    "target_amount": 20000.0,
                    "score": 0.85,
                    "explanation": "Multiple equal candidates",
                }
            ],
        },
    }

    response = client.post("/api/v1/cases", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "AMBIGUOUS"
    assert data["status"] != "CONFIRMED"
    assert data["requires_review"] is True


def test_submit_text_evidence(client: TestClient) -> None:
    payload = {
        "text": "[23/08/26, 2:30 PM] Rahul Kumar: ₹35,000 sent via UPI 408219381920",
        "source_name": "whatsapp.txt",
    }
    response = client.post("/api/v1/cases/text", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "TXT-CASE-" in data["case_id"]
    assert len(data["stage_execution"]) == 8


def test_submit_files_evidence(client: TestClient) -> None:
    file_content = b"Date,Narration,Amount,Direction,Reference\n2026-08-23,UPI/Rahul/408219381920,35000,CREDIT,408219381920\n"
    files = [("files", ("bank_stmt.csv", file_content, "text/csv"))]
    response = client.post("/api/v1/cases/files", files=files)
    assert response.status_code == 200
    data = response.json()
    assert "UPLOAD-CASE-" in data["case_id"]
    assert len(data["stage_execution"]) == 8
