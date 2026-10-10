"""Evaluation runner for VERITY Contradiction Detection subsystem."""

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

from backend.contradiction_detection.detector import ContradictionDetector
from backend.deduplication.result import DeduplicationGroup
from backend.domain.claim import Claim
from backend.domain.transaction import Transaction
from backend.transaction_matching.result import MatchRelationship


def evaluate_contradictions() -> bool:
    print("=" * 70)
    print("VERITY CONTRADICTION DETECTION EVALUATION & FALSE-POSITIVE AUDIT")
    print("=" * 70)

    fixtures_path = root_dir / "data" / "samples" / "day7" / "contradiction_cases.json"
    if not fixtures_path.exists():
        print(f"[ERROR] Fixtures file not found: {fixtures_path}")
        return False

    with open(fixtures_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    detector = ContradictionDetector()
    test_cases = data.get("test_cases", [])
    print(f"Running {len(test_cases)} contradiction evaluation scenarios...\n")

    passed_count = 0
    false_contradictions = 0
    type_counts = {}
    severity_counts = {}
    correctly_avoided = 0

    for tc in test_cases:
        cid = tc["case_id"]
        desc = tc["description"]
        claims = [Claim.model_validate(c) for c in tc.get("claims", [])]
        transactions = [Transaction.model_validate(t) for t in tc.get("transactions", [])]
        entity_map = tc.get("claim_entity_map", {})
        dedup_groups = [DeduplicationGroup.model_validate(g) for g in tc.get("deduplication_groups", [])]
        match_rels = [MatchRelationship.model_validate(m) for m in tc.get("match_relationships", [])]

        result = detector.detect(
            claims=claims,
            transactions=transactions,
            deduplication_groups=dedup_groups,
            match_relationships=match_rels,
            claim_entity_map=entity_map,
        )

        for d in result.discrepancies:
            type_counts[d.discrepancy_type.value] = type_counts.get(d.discrepancy_type.value, 0) + 1
            severity_counts[d.severity.value] = severity_counts.get(d.severity.value, 0) + 1

        expected_types = set(tc.get("expected_discrepancy_types", []))
        expected_count = tc.get("expected_discrepancy_count", 0)

        actual_types = {d.discrepancy_type.value for d in result.discrepancies}
        actual_count = len(result.discrepancies)

        # Audit False Contradictions: If expected was 0 (e.g. partial payment, date tolerance), but got > 0
        if expected_count == 0 and actual_count > 0:
            false_contradictions += actual_count
            print(f"[CRITICAL FAIL - FALSE CONTRADICTION] {cid}: Expected 0 discrepancies, but got {actual_types}")
            continue

        if expected_count == 0 and actual_count == 0:
            correctly_avoided += 1

        # Check correctness
        count_ok = (actual_count == expected_count)
        types_ok = (expected_types == actual_types)

        if count_ok and types_ok:
            passed_count += 1
            summary_str = ", ".join(actual_types) if actual_types else "NO_CONTRADICTION"
            print(f"  [PASS] {cid:<36} -> {actual_count} Contradictions ({summary_str})")
        else:
            print(f"  [FAIL] {cid:<36} -> Got {actual_count} ({actual_types}), Expected {expected_count} ({expected_types})")

    print("\n" + "-" * 70)
    print("EVALUATION METRICS & BREAKDOWN")
    print("-" * 70)
    print(f"Total Scenarios Evaluated       : {len(test_cases)}")
    print(f"Scenarios Passed                : {passed_count} / {len(test_cases)} ({passed_count/len(test_cases)*100:.1f}%)")
    print(f"Contradictions Correctly Avoided: {correctly_avoided}")
    print(f"False Contradictions Detected   : {false_contradictions} (TARGET: 0)")
    print(f"False Contradiction Rate        : {false_contradictions/len(test_cases)*100:.1f}%")
    print("\nContradiction Types Distribution:")
    for dt, count in sorted(type_counts.items()):
        print(f"  * {dt:<30}: {count:>2} discrepancies")
    print("\nSeverity Distribution:")
    for sev, count in sorted(severity_counts.items()):
        print(f"  * {sev:<30}: {count:>2} discrepancies")

    success = (passed_count == len(test_cases)) and (false_contradictions == 0)
    print("=" * 70)
    if success:
        print("VERITY CONTRADICTION DETECTION VERIFICATION SUCCESSFUL (100% Correct, 0% False Positives)")
    else:
        print("[FAIL] Contradiction detection verification failed.")
    print("=" * 70)
    return success


if __name__ == "__main__":
    ok = evaluate_contradictions()
    sys.exit(0 if ok else 1)
