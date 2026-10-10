"""Generate Day 7 Contradiction Detection sample fixtures and cases."""

import json
from pathlib import Path


def create_day7_samples() -> None:
    samples_dir = Path("data/samples/day7")
    samples_dir.mkdir(parents=True, exist_ok=True)

    test_cases = [
        {
            "case_id": "DAY7-01-AMOUNT-MISMATCH",
            "description": "Invoice ₹20,000 vs Bank settlement ₹18,000 -> AMOUNT_MISMATCH",
            "claims": [{
                "id": "CLM-01",
                "evidence_id": "EVID-01",
                "claim_type": "INVOICE_ISSUED",
                "claimed_amount": 20000.0,
                "reference_id_hint": "408219381920",
            }],
            "transactions": [{
                "id": "TXN-01",
                "amount": 18000.0,
                "direction": "CREDIT",
                "bank_reference": "408219381920",
                "evidence_ids": ["EVID-01-BANK"],
            }],
            "expected_discrepancy_types": ["AMOUNT_MISMATCH"],
            "expected_discrepancy_count": 1,
        },
        {
            "case_id": "DAY7-02-REFERENCE-MISMATCH",
            "description": "Bank UTR 408219381920 vs Screenshot UTR 999888777666 -> REFERENCE_MISMATCH",
            "claims": [{
                "id": "CLM-02",
                "evidence_id": "EVID-02",
                "claim_type": "PAYMENT_SENT",
                "claimed_amount": 20000.0,
                "reference_id_hint": "999888777666",
            }],
            "transactions": [{
                "id": "TXN-02",
                "amount": 20000.0,
                "direction": "CREDIT",
                "bank_reference": "408219381920",
                "origin_entity_id": "ENT-001",
                "evidence_ids": ["EVID-02-BANK"],
            }],
            "claim_entity_map": {"CLM-02": "ENT-001"},
            "expected_discrepancy_types": ["REFERENCE_MISMATCH"],
            "expected_discrepancy_count": 1,
        },
        {
            "case_id": "DAY7-03-ENTITY-MISMATCH",
            "description": "Claim for Rahul Kumar (ENT-RAHUL) vs Bank transaction for Rohit Sharma (ENT-ROHIT) -> ENTITY_MISMATCH",
            "claims": [{
                "id": "CLM-03",
                "evidence_id": "EVID-03",
                "claim_type": "INVOICE_ISSUED",
                "claimed_amount": 25000.0,
                "reference_id_hint": "408219381920",
                "counterparty_hint": "Rahul Kumar",
            }],
            "transactions": [{
                "id": "TXN-03",
                "amount": 25000.0,
                "direction": "CREDIT",
                "bank_reference": "408219381920",
                "origin_entity_id": "ENT-ROHIT",
                "evidence_ids": ["EVID-03-BANK"],
            }],
            "claim_entity_map": {"CLM-03": "ENT-RAHUL"},
            "expected_discrepancy_types": ["ENTITY_MISMATCH"],
            "expected_discrepancy_count": 1,
        },
        {
            "case_id": "DAY7-04-VALID-PARTIAL-PAYMENT",
            "description": "Invoice ₹20,000 vs Payment ₹12,000 identified as PARTIAL by Day 5 -> NO FALSE AMOUNT CONTRADICTION",
            "claims": [{
                "id": "CLM-04",
                "evidence_id": "EVID-04",
                "claim_type": "INVOICE_ISSUED",
                "claimed_amount": 20000.0,
                "counterparty_hint": "Priya Patel",
            }],
            "transactions": [{
                "id": "TXN-04",
                "amount": 12000.0,
                "direction": "CREDIT",
                "origin_entity_id": "ENT-PRIYA",
                "evidence_ids": ["EVID-04-BANK"],
            }],
            "match_relationships": [{
                "id": "MAT-04",
                "relationship_type": "PARTIAL",
                "status": "MATCHED",
                "source_claim_ids": ["CLM-04"],
                "target_transaction_ids": ["TXN-04"],
                "matched_amount": 12000.0,
                "target_amount": 20000.0,
                "score": 0.95,
                "explanation": "Partial payment",
            }],
            "claim_entity_map": {"CLM-04": "ENT-PRIYA"},
            "expected_discrepancy_types": [],
            "expected_discrepancy_count": 0,
        },
        {
            "case_id": "DAY7-05-DATE-TOLERANCE",
            "description": "Invoice Aug 20 vs Payment Aug 22 (2-day normal settlement) -> NO FALSE DATE CONTRADICTION",
            "claims": [{
                "id": "CLM-05",
                "evidence_id": "EVID-05",
                "claim_type": "INVOICE_ISSUED",
                "claimed_amount": 15000.0,
                "claimed_date": "2026-08-20",
                "reference_id_hint": "408219381920",
            }],
            "transactions": [{
                "id": "TXN-05",
                "amount": 15000.0,
                "direction": "CREDIT",
                "bank_reference": "408219381920",
                "timestamp": "2026-08-22T10:00:00Z",
                "evidence_ids": ["EVID-05-BANK"],
            }],
            "expected_discrepancy_types": [],
            "expected_discrepancy_count": 0,
        },
        {
            "case_id": "DAY7-06-EXTREME-DATE-MISMATCH",
            "description": "Invoice Aug 1 vs Transaction Sep 30 (60 days drift) -> DATE_MISMATCH",
            "claims": [{
                "id": "CLM-06",
                "evidence_id": "EVID-06",
                "claim_type": "INVOICE_ISSUED",
                "claimed_amount": 30000.0,
                "claimed_date": "2026-08-01",
                "reference_id_hint": "408219381920",
            }],
            "transactions": [{
                "id": "TXN-06",
                "amount": 30000.0,
                "direction": "CREDIT",
                "bank_reference": "408219381920",
                "timestamp": "2026-09-30T10:00:00Z",
                "evidence_ids": ["EVID-06-BANK"],
            }],
            "expected_discrepancy_types": ["DATE_MISMATCH"],
            "expected_discrepancy_count": 1,
        },
        {
            "case_id": "DAY7-07-CONFLICTING-CLAIMS",
            "description": "Claim A ₹20,000 vs Claim B ₹25,000 inside same event group -> CONFLICTING_CLAIMS",
            "claims": [
                {
                    "id": "CLM-07A",
                    "evidence_id": "EVID-07A",
                    "claim_type": "PAYMENT_SENT",
                    "claimed_amount": 20000.0,
                },
                {
                    "id": "CLM-07B",
                    "evidence_id": "EVID-07B",
                    "claim_type": "PAYMENT_SENT",
                    "claimed_amount": 25000.0,
                },
            ],
            "transactions": [],
            "deduplication_groups": [{
                "group_id": "GRP-07",
                "status": "SAME_EVENT",
                "member_evidence_ids": ["EVID-07A", "EVID-07B"],
                "member_claim_ids": ["CLM-07A", "CLM-07B"],
                "explanation": "Grouped",
            }],
            "expected_discrepancy_types": ["CONFLICTING_CLAIMS"],
            "expected_discrepancy_count": 1,
        },
        {
            "case_id": "DAY7-08-DIRECTION-CONFLICT",
            "description": "Expected inflow invoice credit but debit observed -> DIRECTION_MISMATCH",
            "claims": [{
                "id": "CLM-08",
                "evidence_id": "EVID-08",
                "claim_type": "INVOICE_ISSUED",
                "claimed_amount": 10000.0,
                "reference_id_hint": "408219381920",
            }],
            "transactions": [{
                "id": "TXN-08",
                "amount": 10000.0,
                "direction": "DEBIT",
                "bank_reference": "408219381920",
                "evidence_ids": ["EVID-08-BANK"],
            }],
            "match_relationships": [{
                "id": "MAT-08",
                "relationship_type": "ONE_TO_ONE",
                "status": "CONFLICTING",
                "source_claim_ids": ["CLM-08"],
                "target_transaction_ids": ["TXN-08"],
                "matched_amount": 10000.0,
                "target_amount": 10000.0,
                "score": 0.50,
                "explanation": "Direction mismatch",
            }],
            "expected_discrepancy_types": ["DIRECTION_MISMATCH"],
            "expected_discrepancy_count": 1,
        },
        {
            "case_id": "DAY7-09-PAYMENT-RAIL-COMPATIBILITY",
            "description": "GPay payment method hint vs UPI bank rail -> NO FALSE CONTRADICTION",
            "claims": [{
                "id": "CLM-09",
                "evidence_id": "EVID-09",
                "claim_type": "PAYMENT_SENT",
                "claimed_amount": 5000.0,
                "payment_method_hint": "GPAY",
                "reference_id_hint": "408219381920",
            }],
            "transactions": [{
                "id": "TXN-09",
                "amount": 5000.0,
                "direction": "CREDIT",
                "payment_method": "UPI",
                "bank_reference": "408219381920",
                "evidence_ids": ["EVID-09-BANK"],
            }],
            "expected_discrepancy_types": [],
            "expected_discrepancy_count": 0,
        },
        {
            "case_id": "DAY7-10-MULTILINGUAL-EQUIVALENCE",
            "description": "Multilingual claims with equivalent normalized amounts -> NO FALSE CONTRADICTION",
            "claims": [
                {
                    "id": "CLM-10A",
                    "evidence_id": "EVID-10A",
                    "claim_type": "PAYMENT_SENT",
                    "claimed_amount": 20000.0,
                },
                {
                    "id": "CLM-10B",
                    "evidence_id": "EVID-10B",
                    "claim_type": "PAYMENT_SENT",
                    "claimed_amount": 20000.0,
                },
            ],
            "transactions": [],
            "deduplication_groups": [{
                "group_id": "GRP-10",
                "status": "SAME_EVENT",
                "member_evidence_ids": ["EVID-10A", "EVID-10B"],
                "member_claim_ids": ["CLM-10A", "CLM-10B"],
                "explanation": "Multilingual equivalents",
            }],
            "expected_discrepancy_types": [],
            "expected_discrepancy_count": 0,
        },
        {
            "case_id": "DAY7-11-MISSING-AMOUNT",
            "description": "Claim without stated amount ('I sent the money') vs Bank ₹20,000 -> NO FALSE AMOUNT CONTRADICTION",
            "claims": [{
                "id": "CLM-11",
                "evidence_id": "EVID-11",
                "claim_type": "PAYMENT_SENT",
                "claimed_amount": None,
                "reference_id_hint": "408219381920",
            }],
            "transactions": [{
                "id": "TXN-11",
                "amount": 20000.0,
                "direction": "CREDIT",
                "bank_reference": "408219381920",
                "evidence_ids": ["EVID-11-BANK"],
            }],
            "expected_discrepancy_types": [],
            "expected_discrepancy_count": 0,
        },
        {
            "case_id": "DAY7-12-UNRELATED-DISTINCT-EVENTS",
            "description": "Two unrelated ₹20,000 transactions for different parties -> NO FALSE CONTRADICTION",
            "claims": [
                {
                    "id": "CLM-12A",
                    "evidence_id": "E1",
                    "claim_type": "INVOICE_ISSUED",
                    "claimed_amount": 20000.0,
                    "counterparty_hint": "Client A",
                },
                {
                    "id": "CLM-12B",
                    "evidence_id": "E2",
                    "claim_type": "INVOICE_ISSUED",
                    "claimed_amount": 20000.0,
                    "counterparty_hint": "Client B",
                },
            ],
            "transactions": [
                {
                    "id": "TXN-12A",
                    "amount": 20000.0,
                    "direction": "CREDIT",
                    "origin_entity_id": "ENT-A",
                },
                {
                    "id": "TXN-12B",
                    "amount": 20000.0,
                    "direction": "CREDIT",
                    "origin_entity_id": "ENT-B",
                },
            ],
            "claim_entity_map": {"CLM-12A": "ENT-A", "CLM-12B": "ENT-B"},
            "expected_discrepancy_types": [],
            "expected_discrepancy_count": 0,
        },
    ]

    output_file = samples_dir / "contradiction_cases.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({"test_cases": test_cases}, f, indent=2, ensure_ascii=False)

    print(f"Day 7 contradiction cases generated at {output_file}")


if __name__ == "__main__":
    create_day7_samples()
