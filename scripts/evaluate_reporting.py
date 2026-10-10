"""Evaluation runner for VERITY Financial Truth Reporting subsystem."""

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
from backend.domain.entity import Entity
from backend.domain.evidence import Evidence
from backend.domain.transaction import Transaction
from backend.reconciliation.result import ReconciliationResult
from backend.reporting.models import FinancialTruthReport, ReportStatus
from backend.reporting.service import ReportingService
from backend.transaction_matching.result import MatchRelationship


def evaluate_reporting() -> bool:
    print("=" * 70)
    print("VERITY FINANCIAL TRUTH REPORTING EVALUATION & AUDIT")
    print("=" * 70)

    fixtures_path = root_dir / "data" / "samples" / "day9" / "reporting_cases.json"
    if not fixtures_path.exists():
        print(f"[ERROR] Fixtures file not found: {fixtures_path}")
        return False

    with open(fixtures_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    service = ReportingService()
    test_cases = data.get("test_cases", [])
    print(f"Running {len(test_cases)} reporting evaluation scenarios...\n")

    passed_count = 0
    hallucination_violations = 0
    provenance_violations = 0
    serialization_errors = 0
    status_counts = {}

    for tc in test_cases:
        cid = tc["case_id"]
        desc = tc["description"]
        claims = [Claim.model_validate(c) for c in tc.get("claims", [])]
        transactions = [Transaction.model_validate(t) for t in tc.get("transactions", [])]
        evidence = [Evidence.model_validate(e) for e in tc.get("evidence", [])]
        entities = [Entity.model_validate(en) for en in tc.get("entities", [])]
        match_rels = [MatchRelationship.model_validate(m) for m in tc.get("match_relationships", [])]
        dedup_groups = [DeduplicationGroup.model_validate(g) for g in tc.get("deduplication_groups", [])]
        discrepancies = [Discrepancy.model_validate(d) for d in tc.get("discrepancies", [])]
        recon_result = ReconciliationResult.model_validate(tc["reconciliation_result"])

        report = service.build_report(
            reconciliation_result=recon_result,
            claims=claims,
            transactions=transactions,
            evidence=evidence,
            entities=entities,
            match_relationships=match_rels,
            deduplication_groups=dedup_groups,
            discrepancies=discrepancies,
            case_id=cid,
        )

        status_counts[report.status.value] = status_counts.get(report.status.value, 0) + 1

        # Audit 1: Status Propagation
        expected_status_str = tc.get("expected_report_status")
        if report.status.value != expected_status_str:
            print(f"[FAIL - STATUS MISMATCH] {cid}: Got {report.status.value}, Expected {expected_status_str}")
            continue

        # Audit 2: Anti-Hallucination Checks
        # Verify that reported matched amount matches reconciliation result authoritative amount
        if report.financial_summary.matched_amount != recon_result.matched_amount:
            hallucination_violations += 1
            print(f"[CRITICAL FAIL - HALLUCINATED AMOUNT] {cid}: Report matched amount {report.financial_summary.matched_amount} != Recon {recon_result.matched_amount}")
            continue

        # If claim amount was None, report must reflect None, not an invented number
        if any(c.claimed_amount is None for c in claims) and len(claims) == 1 and not recon_result.expected_amount:
            if report.financial_summary.claimed_amount is not None:
                hallucination_violations += 1
                print(f"[CRITICAL FAIL - INVENTED AMOUNT] {cid}: Claim amount was None, but report invented {report.financial_summary.claimed_amount}")
                continue

        # Audit 3: Provenance References
        if not report.provenance.reconciliation_id:
            provenance_violations += 1
            print(f"[FAIL - MISSING PROVENANCE] {cid}: Reconciliation ID missing in provenance references.")
            continue

        # Audit 4: Serialization
        try:
            json_str = service.render_json_report(report)
            text_str = service.render_text_report(report)
            assert len(json_str) > 50
            assert len(text_str) > 100
        except Exception as e:
            serialization_errors += 1
            print(f"[FAIL - SERIALIZATION] {cid}: Error rendering text or JSON: {e}")
            continue

        passed_count += 1
        conf_pct = int(report.confidence_score * 100)
        print(f"  [PASS] {cid:<36} -> {report.status.value:<18} | Conf: {conf_pct:>3}% | Actions: {len(report.recommended_actions)}")

    print("\n" + "-" * 70)
    print("EVALUATION METRICS & AUDIT BREAKDOWN")
    print("-" * 70)
    print(f"Total Scenarios Evaluated       : {len(test_cases)}")
    print(f"Scenarios Passed                : {passed_count} / {len(test_cases)} ({passed_count/len(test_cases)*100:.1f}%)")
    print(f"Hallucination Violations        : {hallucination_violations} (TARGET: 0)")
    print(f"Provenance Violations           : {provenance_violations} (TARGET: 0)")
    print(f"Serialization Errors            : {serialization_errors} (TARGET: 0)")
    print("\nReport Status Distribution:")
    for stat, count in sorted(status_counts.items()):
        print(f"  * {stat:<28}: {count:>2} reports")

    success = (passed_count == len(test_cases)) and (hallucination_violations == 0) and (provenance_violations == 0) and (serialization_errors == 0)
    print("=" * 70)
    if success:
        print("VERITY FINANCIAL TRUTH REPORTING VERIFICATION SUCCESSFUL (100% Correct, 0 Hallucinations)")
    else:
        print("[FAIL] Reporting verification failed.")
    print("=" * 70)
    return success


if __name__ == "__main__":
    ok = evaluate_reporting()
    sys.exit(0 if ok else 1)
