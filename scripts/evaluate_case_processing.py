"""Evaluation runner for VERITY End-to-End Case Processing Pipeline."""

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

from backend.case_processing.models import CaseInput
from backend.case_processing.service import CaseProcessingService
from backend.domain.entity import Entity
from backend.domain.evidence import Evidence
from backend.domain.transaction import Transaction


def evaluate_case_processing() -> bool:
    print("=" * 70)
    print("VERITY END-TO-END FINANCE CONTROLLER PIPELINE EVALUATION")
    print("=" * 70)

    fixtures_path = root_dir / "data" / "samples" / "day10" / "case_processing_cases.json"
    if not fixtures_path.exists():
        print(f"[ERROR] Fixtures file not found: {fixtures_path}")
        return False

    with open(fixtures_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    service = CaseProcessingService()
    test_cases = data.get("test_cases", [])
    print(f"Running {len(test_cases)} end-to-end case processing evaluation scenarios...\n")

    passed_count = 0
    false_confirmations = 0
    double_count_errors = 0
    stage_telemetry_errors = 0
    provenance_errors = 0
    status_counts = {}
    latencies = []

    for tc in test_cases:
        cid = tc["case_id"]
        desc = tc["description"]
        ev_items = [Evidence.model_validate(e) for e in tc.get("evidence", [])]
        claims = tc.get("claims", [])
        txns = [Transaction.model_validate(t) for t in tc.get("transactions", [])]
        entities = [Entity.model_validate(en) for en in tc.get("entities", [])]
        metadata = tc.get("metadata", {})
        if claims:
            metadata["precomputed_claims"] = claims

        case_in = CaseInput(
            case_id=cid,
            evidence_items=ev_items,
            transactions=txns,
            entities=entities,
            metadata=metadata,
        )

        result = service.process_case(case_in)
        latencies.append(result.total_execution_time_ms)
        status_counts[result.status] = status_counts.get(result.status, 0) + 1

        expected_status = tc.get("expected_status")
        expected_matched = tc.get("expected_matched_amount")
        expected_outstanding = tc.get("expected_outstanding_amount")

        # Audit 1: False Confirmation
        if expected_status in ("CONTRADICTED", "UNVERIFIABLE", "AMBIGUOUS") and result.status == "CONFIRMED":
            false_confirmations += 1
            print(f"[CRITICAL FAIL - FALSE CONFIRMATION] {cid}: Expected {expected_status}, but got CONFIRMED!")
            continue

        # Audit 2: Double Counting Error
        if expected_matched is not None and result.financial_summary.get("matched_amount", 0.0) > expected_matched:
            double_count_errors += 1
            print(f"[CRITICAL FAIL - DOUBLE COUNTING] {cid}: Matched {result.financial_summary.get('matched_amount')} > Expected {expected_matched}")
            continue

        # Audit 3: Stage Telemetry
        if len(result.stage_records) != 8:
            stage_telemetry_errors += 1
            print(f"[FAIL - STAGE TELEMETRY] {cid}: Expected 8 stages recorded, got {len(result.stage_records)}")
            continue

        # Audit 4: Provenance Node Count
        if result.provenance_node_count == 0 and len(ev_items) > 0:
            provenance_errors += 1
            print(f"[FAIL - PROVENANCE] {cid}: Provenance DAG recorded 0 nodes.")
            continue

        # Check status and amounts
        status_ok = (result.status == expected_status or (expected_status == "PARTIALLY_SETTLED" and result.status in ("PARTIAL", "PARTIALLY_SETTLED")))
        matched_ok = (expected_matched is None or abs(result.financial_summary.get("matched_amount", 0.0) - expected_matched) <= 0.01)
        outstanding_ok = (expected_outstanding is None or abs(result.financial_summary.get("outstanding_amount", 0.0) - expected_outstanding) <= 0.01)

        if status_ok and matched_ok and outstanding_ok:
            passed_count += 1
            m_str = f"INR {result.financial_summary.get('matched_amount', 0.0):,.2f}"
            out_str = f"Out: INR {result.financial_summary.get('outstanding_amount', 0.0):,.2f}" if result.financial_summary.get('outstanding_amount', 0.0) > 0 else "Settled"
            print(f"  [PASS] {cid:<36} -> {result.status:<18} | {m_str:<15} | {out_str:<16} | {result.total_execution_time_ms:>5.1f}ms")
        else:
            print(f"  [FAIL] {cid:<36} -> Got {result.status} (Exp: {expected_status}), Matched: {result.financial_summary.get('matched_amount')} (Exp: {expected_matched})")

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    print("\n" + "-" * 70)
    print("EVALUATION METRICS & AUDIT BREAKDOWN")
    print("-" * 70)
    print(f"Total Scenarios Evaluated       : {len(test_cases)}")
    print(f"Scenarios Passed                : {passed_count} / {len(test_cases)} ({passed_count/len(test_cases)*100:.1f}%)")
    print(f"False Confirmations Detected    : {false_confirmations} (TARGET: 0)")
    print(f"Double-Counting Errors          : {double_count_errors} (TARGET: 0)")
    print(f"Stage Telemetry Errors          : {stage_telemetry_errors} (TARGET: 0)")
    print(f"Provenance Errors               : {provenance_errors} (TARGET: 0)")
    print(f"Average Pipeline Latency        : {avg_latency:.2f} ms")
    print("\nPipeline Status Distribution:")
    for stat, count in sorted(status_counts.items()):
        print(f"  * {stat:<28}: {count:>2} cases")

    success = (passed_count == len(test_cases)) and (false_confirmations == 0) and (double_count_errors == 0) and (stage_telemetry_errors == 0)
    print("=" * 70)
    if success:
        print("VERITY END-TO-END PIPELINE VERIFICATION SUCCESSFUL (100% Correct, 0 Safety Violations)")
    else:
        print("[FAIL] End-to-end pipeline verification failed.")
    print("=" * 70)
    return success


if __name__ == "__main__":
    ok = evaluate_case_processing()
    sys.exit(0 if ok else 1)
