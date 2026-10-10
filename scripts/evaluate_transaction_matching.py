"""Evaluation runner for VERITY Transaction Matching subsystem."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.domain.claim import Claim
from backend.domain.transaction import Transaction
from backend.transaction_matching.engine import TransactionMatcher


def evaluate_transaction_matching() -> bool:
    print("=" * 70)
    print("VERITY TRANSACTION MATCHING EVALUATION & FALSE-MATCH AUDIT")
    print("=" * 70)

    fixtures_path = root_dir / "data" / "samples" / "day5" / "transaction_matching_cases.json"
    if not fixtures_path.exists():
        print(f"[ERROR] Fixtures file not found: {fixtures_path}")
        return False

    with open(fixtures_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    matcher = TransactionMatcher()
    test_cases = data.get("test_cases", [])
    print(f"Running {len(test_cases)} transaction matching evaluation scenarios...\n")

    passed_count = 0
    false_matches = 0
    topology_counts = {}
    status_counts = {}

    for tc in test_cases:
        cid = tc["case_id"]
        desc = tc["description"]
        claims = [Claim.model_validate(c) for c in tc.get("claims", [])]
        transactions = [Transaction.model_validate(t) for t in tc.get("transactions", [])]
        entity_map = tc.get("claim_entity_map", {})

        result = matcher.match(
            claims=claims,
            transactions=transactions,
            claim_entity_map=entity_map,
        )

        # Update metrics
        for r in result.relationships:
            topology_counts[r.relationship_type.value] = topology_counts.get(r.relationship_type.value, 0) + 1
            status_counts[r.status.value] = status_counts.get(r.status.value, 0) + 1

        # Check Unmatched case (DAY5-12)
        if "expected_unmatched_txns" in tc:
            expected_unmatched = set(tc["expected_unmatched_txns"])
            actual_unmatched = set(result.unmatched_transaction_ids)
            if expected_unmatched == actual_unmatched and len(result.relationships) == 0:
                passed_count += 1
                print(f"  [PASS] {cid:<34} -> UNMATCHED (Zero false matches)")
            else:
                print(f"  [FAIL] {cid:<34} -> Expected unmatched {expected_unmatched}, got {result.relationships}")
            continue

        # Check Match Relationships
        expected_topo = tc.get("expected_topology")
        expected_status = tc.get("expected_status")

        if not result.relationships:
            print(f"  [FAIL] {cid:<34} -> No relationship created (Expected {expected_topo}/{expected_status})")
            continue

        primary_rel = result.relationships[0]

        # Audit False Match: If expected is AMBIGUOUS or CONFLICTING, but status became MATCHED
        is_false_match = False
        if expected_status in ("AMBIGUOUS", "CONFLICTING") and primary_rel.status.value == "MATCHED":
            is_false_match = True

        if is_false_match:
            false_matches += 1
            print(f"[CRITICAL FAIL - FALSE MATCH] {cid}: Expected {expected_status}, got {primary_rel.status.value}")
            print(f"  Explanation: {primary_rel.explanation}")
            continue

        # Check correctness
        status_ok = (primary_rel.status.value == expected_status)
        topo_ok = (primary_rel.relationship_type.value == expected_topo)

        if status_ok and topo_ok:
            passed_count += 1
            print(f"  [PASS] {cid:<34} -> {primary_rel.relationship_type.value:<12} | {primary_rel.status.value:<11} (Score: {primary_rel.score})")
        else:
            print(f"  [FAIL] {cid:<34} -> Got {primary_rel.relationship_type.value}/{primary_rel.status.value} (Expected {expected_topo}/{expected_status})")
            print(f"         Explanation: {primary_rel.explanation}")

    print("\n" + "-" * 70)
    print("EVALUATION METRICS & BREAKDOWN")
    print("-" * 70)
    print(f"Total Scenarios Evaluated   : {len(test_cases)}")
    print(f"Scenarios Passed            : {passed_count} / {len(test_cases)} ({passed_count/len(test_cases)*100:.1f}%)")
    print(f"False Matches Detected      : {false_matches} (TARGET: 0)")
    print(f"False Match Rate            : {false_matches/len(test_cases)*100:.1f}%")
    print("\nRelationship Topologies Breakdown:")
    for topo, count in sorted(topology_counts.items()):
        print(f"  * {topo:<15}: {count:>2} relationships")
    print("\nRelationship Status Breakdown:")
    for stat, count in sorted(status_counts.items()):
        print(f"  * {stat:<15}: {count:>2} relationships")

    success = (passed_count == len(test_cases)) and (false_matches == 0)
    print("=" * 70)
    if success:
        print("VERITY TRANSACTION MATCHING VERIFICATION SUCCESSFUL (100% Correct, 0% False Matches)")
    else:
        print("[FAIL] Transaction matching verification failed.")
    print("=" * 70)
    return success


if __name__ == "__main__":
    ok = evaluate_transaction_matching()
    sys.exit(0 if ok else 1)
