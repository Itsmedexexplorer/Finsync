"""Evaluation runner for VERITY Cross-Modal Deduplication subsystem."""

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

from backend.deduplication.engine import DeduplicationEngine
from backend.domain.claim import Claim
from backend.domain.evidence import Evidence
from backend.domain.transaction import Transaction
from backend.transaction_matching.result import MatchRelationship


def evaluate_deduplication() -> bool:
    print("=" * 70)
    print("VERITY CROSS-MODAL DEDUPLICATION EVALUATION & FALSE-MERGE AUDIT")
    print("=" * 70)

    fixtures_path = root_dir / "data" / "samples" / "day6" / "deduplication_cases.json"
    if not fixtures_path.exists():
        print(f"[ERROR] Fixtures file not found: {fixtures_path}")
        return False

    with open(fixtures_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    engine = DeduplicationEngine()
    test_cases = data.get("test_cases", [])
    print(f"Running {len(test_cases)} deduplication evaluation scenarios...\n")

    passed_count = 0
    false_merges = 0
    status_counts = {}

    for tc in test_cases:
        cid = tc["case_id"]
        desc = tc["description"]
        evidence_items = [Evidence.model_validate(e) for e in tc.get("evidence_items", [])]
        claims = [Claim.model_validate(c) for c in tc.get("claims", [])]
        transactions = [Transaction.model_validate(t) for t in tc.get("transactions", [])]
        entity_map = tc.get("claim_entity_map", {})
        match_rels = [MatchRelationship.model_validate(m) for m in tc.get("match_relationships", [])]

        result = engine.deduplicate(
            evidence_items=evidence_items,
            claims=claims,
            transactions=transactions,
            claim_entity_map=entity_map,
            match_relationships=match_rels,
        )

        for g in result.groups:
            status_counts[g.status.value] = status_counts.get(g.status.value, 0) + 1

        expected_status = tc.get("expected_status")
        expected_group_count = tc.get("expected_group_count")

        # Audit False Merge: If expected DISTINCT_EVENT or AMBIGUOUS, but got merged into 1 SAME_EVENT
        is_false_merge = False
        if expected_status == "DISTINCT_EVENT" and len(result.groups) == 1 and result.groups[0].status.value == "SAME_EVENT":
            is_false_merge = True

        if is_false_merge:
            false_merges += 1
            print(f"[CRITICAL FAIL - FALSE MERGE] {cid}: Distinct events were incorrectly collapsed into one!")
            continue

        # Check group count and status
        count_ok = (expected_group_count is None or len(result.groups) == expected_group_count)
        status_ok = True
        if expected_status:
            status_ok = any(g.status.value == expected_status for g in result.groups)

        if count_ok and status_ok:
            passed_count += 1
            primary_status = result.groups[0].status.value if result.groups else "NONE"
            print(f"  [PASS] {cid:<40} -> {len(result.groups)} Groups | Status: {primary_status}")
        else:
            print(f"  [FAIL] {cid:<40} -> Groups: {len(result.groups)} (Expected {expected_group_count}), Status: {[g.status.value for g in result.groups]}")

    print("\n" + "-" * 70)
    print("EVALUATION METRICS & BREAKDOWN")
    print("-" * 70)
    print(f"Total Scenarios Evaluated   : {len(test_cases)}")
    print(f"Scenarios Passed            : {passed_count} / {len(test_cases)} ({passed_count/len(test_cases)*100:.1f}%)")
    print(f"False Merges Detected       : {false_merges} (TARGET: 0)")
    print(f"False Merge Rate            : {false_merges/len(test_cases)*100:.1f}%")
    print("\nGroup Status Distribution:")
    for stat, count in sorted(status_counts.items()):
        print(f"  * {stat:<28}: {count:>2} groups")

    success = (passed_count == len(test_cases)) and (false_merges == 0)
    print("=" * 70)
    if success:
        print("VERITY DEDUPLICATION VERIFICATION SUCCESSFUL (100% Correct, 0% False Merges)")
    else:
        print("[FAIL] Deduplication verification failed.")
    print("=" * 70)
    return success


if __name__ == "__main__":
    ok = evaluate_deduplication()
    sys.exit(0 if ok else 1)
