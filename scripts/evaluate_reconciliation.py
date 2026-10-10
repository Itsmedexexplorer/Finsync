"""Evaluation runner for VERITY Financial Reconciliation subsystem."""

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

from backend.deduplication.result import DeduplicationGroup
from backend.domain.claim import Claim
from backend.domain.discrepancy import Discrepancy
from backend.domain.evidence import Evidence
from backend.domain.reconciliation import ReconciliationStatus
from backend.domain.transaction import Transaction
from backend.reconciliation.engine import ReconciliationEngine
from backend.transaction_matching.result import MatchRelationship


def evaluate_reconciliation() -> bool:
    print("=" * 70)
    print("VERITY FINANCIAL RECONCILIATION EVALUATION & SAFETY AUDIT")
    print("=" * 70)

    fixtures_path = root_dir / "data" / "samples" / "day8" / "reconciliation_cases.json"
    if not fixtures_path.exists():
        print(f"[ERROR] Fixtures file not found: {fixtures_path}")
        return False

    with open(fixtures_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    engine = ReconciliationEngine()
    test_cases = data.get("test_cases", [])
    print(f"Running {len(test_cases)} reconciliation evaluation scenarios...\n")

    passed_count = 0
    false_confirmations = 0
    false_contradictions = 0
    double_count_errors = 0
    unsafe_ambiguity_resolutions = 0
    status_counts = {}

    for tc in test_cases:
        cid = tc["case_id"]
        desc = tc["description"]
        claims = [Claim.model_validate(c) for c in tc.get("claims", [])]
        transactions = [Transaction.model_validate(t) for t in tc.get("transactions", [])]
        evidence_items = [Evidence.model_validate(e) for e in tc.get("evidence_items", [])]
        entity_map = tc.get("claim_entity_map", {})
        dedup_groups = [DeduplicationGroup.model_validate(g) for g in tc.get("deduplication_groups", [])]
        match_rels = [MatchRelationship.model_validate(m) for m in tc.get("match_relationships", [])]
        discrepancies = [Discrepancy.model_validate(d) for d in tc.get("discrepancies", [])]

        batch_result = engine.reconcile(
            claims=claims,
            transactions=transactions,
            evidence_items=evidence_items,
            deduplication_groups=dedup_groups,
            match_relationships=match_rels,
            discrepancies=discrepancies,
            claim_entity_map=entity_map,
        )

        expected_status_str = tc.get("expected_status")
        expected_status = ReconciliationStatus(expected_status_str) if expected_status_str else None
        expected_reconciled = tc.get("expected_reconciled_amount")
        expected_outstanding = tc.get("expected_outstanding_amount")

        if not batch_result.results:
            print(f"  [FAIL] {cid:<46} -> No reconciliation result generated!")
            continue

        primary_res = batch_result.results[0]
        status_counts[primary_res.status.value] = status_counts.get(primary_res.status.value, 0) + 1

        # Audit 1: False Confirmation
        # If expected is CONTRADICTED, UNVERIFIABLE, or AMBIGUOUS, but status became CONFIRMED
        if expected_status in (ReconciliationStatus.CONTRADICTED, ReconciliationStatus.UNVERIFIABLE, ReconciliationStatus.AMBIGUOUS) and primary_res.status == ReconciliationStatus.CONFIRMED:
            false_confirmations += 1
            print(f"[CRITICAL FAIL - FALSE CONFIRMATION] {cid}: Expected {expected_status.value}, but got CONFIRMED!")
            continue

        # Audit 2: Unsafe Ambiguity Resolution
        if expected_status == ReconciliationStatus.AMBIGUOUS and primary_res.status != ReconciliationStatus.AMBIGUOUS:
            unsafe_ambiguity_resolutions += 1
            print(f"[CRITICAL FAIL - UNSAFE AMBIGUITY RESOLUTION] {cid}: Ambiguity was improperly resolved to {primary_res.status.value}!")
            continue

        # Audit 3: Double Counting Error
        # In multi-evidence case (DAY8-10), ensure reconciled amount does not multiply evidence count
        if "expected_reconciled_amount" in tc:
            if primary_res.matched_amount > expected_reconciled:
                double_count_errors += 1
                print(f"[CRITICAL FAIL - DOUBLE COUNTING] {cid}: Reconciled ₹{primary_res.matched_amount:,.2f} > Expected ₹{expected_reconciled:,.2f}!")
                continue

        # Check status and amounts
        status_ok = (primary_res.status == expected_status or (expected_status == ReconciliationStatus.PARTIALLY_SETTLED and primary_res.status in (ReconciliationStatus.PARTIAL, ReconciliationStatus.PARTIALLY_SETTLED)))
        reconciled_ok = (expected_reconciled is None or abs(primary_res.matched_amount - expected_reconciled) <= 0.01)
        outstanding_ok = (expected_outstanding is None or abs(primary_res.outstanding_amount - expected_outstanding) <= 0.01)

        if status_ok and reconciled_ok and outstanding_ok:
            passed_count += 1
            reconciled_str = f"₹{primary_res.matched_amount:,.2f}"
            out_str = f"Outstanding: ₹{primary_res.outstanding_amount:,.2f}" if primary_res.outstanding_amount > 0 else "Fully Settled"
            print(f"  [PASS] {cid:<46} -> {primary_res.status.value:<18} | {reconciled_str:<12} | {out_str}")
        else:
            print(f"  [FAIL] {cid:<46} -> Got {primary_res.status.value} (Exp: {expected_status.value if expected_status else 'None'}), Reconciled: {primary_res.matched_amount} (Exp: {expected_reconciled}), Out: {primary_res.outstanding_amount} (Exp: {expected_outstanding})")
            print(f"         Explanation: {primary_res.explanation}")

    print("\n" + "-" * 70)
    print("EVALUATION METRICS & SAFETY BREAKDOWN")
    print("-" * 70)
    print(f"Total Scenarios Evaluated       : {len(test_cases)}")
    print(f"Scenarios Passed                : {passed_count} / {len(test_cases)} ({passed_count/len(test_cases)*100:.1f}%)")
    print(f"False Confirmations Detected    : {false_confirmations} (TARGET: 0)")
    print(f"False Contradictions Detected   : {false_contradictions} (TARGET: 0)")
    print(f"Double-Counting Errors          : {double_count_errors} (TARGET: 0)")
    print(f"Unsafe Ambiguity Resolutions    : {unsafe_ambiguity_resolutions} (TARGET: 0)")
    print("\nReconciliation Status Distribution:")
    for stat, count in sorted(status_counts.items()):
        print(f"  * {stat:<28}: {count:>2} events")

    success = (passed_count == len(test_cases)) and (false_confirmations == 0) and (double_count_errors == 0) and (unsafe_ambiguity_resolutions == 0)
    print("=" * 70)
    if success:
        print("VERITY FINANCIAL RECONCILIATION VERIFICATION SUCCESSFUL (100% Correct, 0 Safety Violations)")
    else:
        print("[FAIL] Financial reconciliation verification failed.")
    print("=" * 70)
    return success


if __name__ == "__main__":
    ok = evaluate_reconciliation()
    sys.exit(0 if ok else 1)
