"""CLI validation script for the VERITY Ground-Truth Benchmark."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from data.benchmark.loader import load_benchmark_cases


def validate_benchmark() -> bool:
    print("=" * 70)
    print("VERITY GROUND-TRUTH BENCHMARK INTEGRITY VALIDATOR")
    print("=" * 70)
    
    benchmark_file = root_dir / "data" / "benchmark" / "ground_truth_cases.json"
    print(f"Loading benchmark from: {benchmark_file}")
    
    try:
        cases = load_benchmark_cases(benchmark_file)
    except Exception as e:
        print(f"[ERROR] Failed to load and validate benchmark cases: {e}")
        return False

    print(f"\n[OK] Successfully parsed and validated {len(cases)} cases into Pydantic models.")
    
    # 1. Category Distribution
    category_counts = Counter(c.category for c in cases)
    print("\n--- Category Breakdown ---")
    for cat, count in sorted(category_counts.items()):
        print(f"  * {cat:<28}: {count:>2} cases")

    # 2. Ground Truth Status Distribution
    status_counts = Counter(c.ground_truth.expected_status.value for c in cases)
    print("\n--- Expected Status Breakdown ---")
    for status, count in sorted(status_counts.items()):
        print(f"  * {status:<28}: {count:>2} cases")

    # 3. Modality Distribution
    modality_counts = Counter(e.modality.value for c in cases for e in c.evidence)
    print("\n--- Evidence Modality Breakdown ---")
    for mod, count in sorted(modality_counts.items()):
        print(f"  * {mod:<28}: {count:>2} items")

    # 4. Integrity Checks
    print("\n--- Running Invariant Checks ---")
    required_categories = [
        "CLEAN_1TO1",
        "ONE_TO_MANY",
        "MANY_TO_ONE",
        "PARTIAL_PAYMENTS",
        "CROSS_MODAL_DUPLICATES",
        "CONTRADICTORY_CLAIMS",
        "MISSING_EVIDENCE",
        "IDENTITY_NAME_VARIATIONS",
        "INCORRECT_REF_IDS",
        "CASH_PAYMENT_CLAIMS",
        "MULTILINGUAL_HINGLISH",
        "AMBIGUOUS_CASES",
    ]
    
    missing_cats = [rc for rc in required_categories if rc not in category_counts]
    if missing_cats:
        print(f"[FAIL] Missing required benchmark categories: {missing_cats}")
        return False
    else:
        print(f"[PASS] All {len(required_categories)} required categories present.")

    # Unique Case IDs check
    case_ids = [c.case_id for c in cases]
    if len(case_ids) != len(set(case_ids)):
        print(f"[FAIL] Duplicate case IDs detected!")
        return False
    else:
        print(f"[PASS] All {len(cases)} case IDs are strictly unique.")

    # Evidence & Claim IDs uniqueness within each case
    for c in cases:
        e_ids = [e.id for e in c.evidence]
        if len(e_ids) != len(set(e_ids)):
            print(f"[FAIL] Duplicate evidence IDs in case {c.case_id}")
            return False
        c_ids = [cl.id for cl in c.claims]
        if len(c_ids) != len(set(c_ids)):
            print(f"[FAIL] Duplicate claim IDs in case {c.case_id}")
            return False

    print("[PASS] All intra-case evidence and claim IDs are valid and unique.")
    print("=" * 70)
    print("BENCHMARK INTEGRITY VERIFICATION SUCCESSFUL (100% Valid)")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = validate_benchmark()
    sys.exit(0 if success else 1)
