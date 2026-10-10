"""Generate Day 4 Entity Resolution sample fixtures and cases."""

import json
from pathlib import Path


def create_day4_samples() -> None:
    samples_dir = Path("data/samples/day4")
    samples_dir.mkdir(parents=True, exist_ok=True)

    entities = [
        {
            "id": "ENT-001",
            "canonical_name": "Rahul Kumar",
            "entity_type": "INDIVIDUAL",
            "pan": "ABCDE1234F",
            "upi_ids": ["rahulkumar@ybl"],
            "phone_numbers": ["+919876543210"],
            "aliases": ["Rahul K"],
        },
        {
            "id": "ENT-002",
            "canonical_name": "Rahul Sharma",
            "entity_type": "INDIVIDUAL",
            "pan": "XYZPK9876A",
            "upi_ids": ["rahul.sharma@okhdfcbank"],
            "phone_numbers": ["+919811022334"],
            "aliases": ["Rahul S", "Sharmaji"],
        },
        {
            "id": "ENT-003",
            "canonical_name": "Rohit Kumar",
            "entity_type": "INDIVIDUAL",
            "upi_ids": ["rohit.k@icici"],
            "phone_numbers": ["+919988776655"],
            "aliases": ["Rohit K"],
        },
        {
            "id": "ENT-004",
            "canonical_name": "Shree Electronics Pvt Ltd",
            "entity_type": "PRIVATE_LIMITED",
            "gstin": "29ABCDE1234F1Z5",
            "upi_ids": ["shree.elec@icici"],
            "aliases": ["Shree Electronics", "Shree Electronics Store", "M/s Shree Electronics"],
        },
    ]

    test_cases = [
        {
            "case_id": "DAY4-CASE-01-EXACT-UPI",
            "description": "Exact UPI VPA identifier match -> CONFIRMED",
            "query": {"query_name": "Rahul Kumar", "query_handle": "rahulkumar@ybl"},
            "expected_status": "CONFIRMED",
            "expected_entity_id": "ENT-001",
        },
        {
            "case_id": "DAY4-CASE-02-NAME-INITIALS",
            "description": "Unique initials variation 'R. Sharma' -> PROBABLE",
            "query": {"query_name": "R. Sharma"},
            "expected_status": "PROBABLE",
            "expected_entity_id": "ENT-002",
        },
        {
            "case_id": "DAY4-CASE-03-AMBIGUOUS-NAME",
            "description": "Ambiguous first name 'Rahul' matching multiple Rahul entities -> AMBIGUOUS",
            "query": {"query_name": "Rahul"},
            "expected_status": "AMBIGUOUS",
            "expected_entity_id": None,
        },
        {
            "case_id": "DAY4-CASE-04-CONFLICTING-SIGNALS",
            "description": "Matching phone number for ENT-001 but conflicting UPI VPA -> CONFLICTING",
            "query": {"query_name": "Rahul Kumar", "query_phone": "9876543210", "query_handle": "unknown_vpa@paytm"},
            "expected_status": "CONFLICTING",
            "expected_entity_id": None,
        },
        {
            "case_id": "DAY4-CASE-05-UNKNOWN-PARTY",
            "description": "Missing / unidentifiable party -> UNRESOLVED",
            "query": {},
            "expected_status": "UNRESOLVED",
            "expected_entity_id": None,
        },
        {
            "case_id": "DAY4-CASE-06-BUSINESS-ALIAS",
            "description": "Trade alias 'Shree Electronics Store' -> CONFIRMED",
            "query": {"query_name": "Shree Electronics Store"},
            "expected_status": "CONFIRMED",
            "expected_entity_id": "ENT-004",
        },
        {
            "case_id": "DAY4-CASE-07-FALSE-MERGE-PREVENTION",
            "description": "Distinct entities 'Rahul Kumar' and 'Rohit Kumar' -> Zero False Merge",
            "query": {"query_name": "Rohit Kumar"},
            "expected_status": "CONFIRMED",
            "expected_entity_id": "ENT-003",
        },
        {
            "case_id": "DAY4-CASE-08-EXACT-GSTIN",
            "description": "Exact GSTIN match -> CONFIRMED",
            "query": {"query_tax_id": "29ABCDE1234F1Z5"},
            "expected_status": "CONFIRMED",
            "expected_entity_id": "ENT-004",
        },
    ]

    data = {
        "registered_entities": entities,
        "test_cases": test_cases,
    }

    output_file = samples_dir / "entity_resolution_cases.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Day 4 entity resolution cases generated at {output_file}")


if __name__ == "__main__":
    create_day4_samples()
