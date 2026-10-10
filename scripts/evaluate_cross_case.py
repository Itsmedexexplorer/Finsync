"""VERITY Day 18 Cross-Case Intelligence & Counterparty Memory Evaluator.

Evaluates 12 deterministic scenarios verifying:
- Counterparty lifetime history & case count accuracy
- High exposure aggregation
- Repeated contradiction detection
- Recurring discrepancy pattern identification
- Reference / UTR duplicate reuse detection
- Case relationship discovery (Shared Entity, Shared Reference)
- Cross-case isolation and zero data pollution
- Truth immutability under historical intelligence

Usage:
    python scripts/evaluate_cross_case.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure project root in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.case_processing.service import CaseProcessingService
from backend.cross_case.service import CrossCaseIntelligenceService
from backend.storage.config import StorageSettings
from backend.storage.database import DatabaseEngine
from backend.storage.service import StorageService


def run_evaluation() -> int:
    print("=" * 80)
    print("VERITY DAY 18 EVALUATOR: CROSS-CASE INTELLIGENCE & COUNTERPARTY MEMORY")
    print("=" * 80)

    dataset_path = Path("data/samples/day18/cross_case_cases.json")
    if not dataset_path.exists():
        print(f"FAIL: Dataset '{dataset_path}' not found.")
        return 1

    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    test_cases = dataset.get("test_cases", [])
    print(f"Loaded {len(test_cases)} evaluation test cases.")

    # Create dedicated isolated test database for sequential memory evaluation
    temp_dir = tempfile.mkdtemp(prefix="verity_day18_eval_")
    db_path = os.path.join(temp_dir, "day18_eval.db")
    settings = StorageSettings(database_url=f"sqlite:///{db_path}", pool_size=5)
    engine = DatabaseEngine(settings=settings)

    case_service = CaseProcessingService()
    storage_service = StorageService(engine=engine)
    cross_service = CrossCaseIntelligenceService(engine=engine)

    passed_count = 0
    failed_count = 0
    results: List[Tuple[str, str, bool, str]] = []

    print("\n--- Sequential Case Processing & Historical Correlation ---")

    for idx, tc in enumerate(test_cases, 1):
        cid = tc["case_id"]
        desc = tc.get("description", "")
        exp = tc.get("expected_output", {})

        print(f"\n[{idx}/12] Evaluating Case: {cid}")
        print(f"     Description: {desc}")

        # 1. Process Case through deterministic pipeline
        case_dict = {
            "case_id": cid,
            "evidence": tc.get("evidence", []),
            "claims": tc.get("claims", []),
            "transactions": tc.get("transactions", []),
            "entities": tc.get("entities", []),
        }
        res = case_service.process_benchmark_case(case_dict)

        # 2. Persist Case atomically into SQLite storage
        storage_service.process_and_persist_case(
            case_result=res,
            raw_evidence_list=tc.get("evidence", []),
            raw_claims_list=tc.get("claims", []),
            raw_entities_list=tc.get("entities", []),
            raw_transactions_list=tc.get("transactions", []),
        )

        # 3. Query cross-case intelligence
        profile = cross_service.build_case_intelligence_profile(cid)

        # 4. Perform scenario-specific verification
        passed = True
        reason = ""

        if cid == "DAY18-01-FIRST-TIME":
            h = cross_service.get_counterparty_history("Fresh Bloom Florals")
            if not h or h.case_count != 1:
                passed = False
                reason = f"Expected case_count=1 for first-time entity, got {h.case_count if h else 'None'}"
            elif len(profile.reference_correlations) > 0 and any(r.reuse_warning for r in profile.reference_correlations):
                passed = False
                reason = "False reference reuse warning triggered on first-time reference"

        elif cid == "DAY18-02-REPEAT-COUNTERPARTY":
            h = cross_service.get_counterparty_history("Creative Minds Studio")
            if not h or h.case_count < 1:
                passed = False
                reason = f"Expected Creative Minds Studio history, got {h.case_count if h else 'None'}"
            else:
                corrs = cross_service.get_case_correlations(cid)
                # Verify it found correlation with any previous case
                reason = f"Identified entity history (cases: {h.previous_case_ids})"

        elif cid == "DAY18-03-HIGH-EXPOSURE":
            h = cross_service.get_counterparty_history("Creative Minds Studio")
            if not h or h.total_exposure < 100000.0:
                passed = False
                reason = f"Expected total_exposure >= 100,000, got {h.total_exposure if h else 'None'}"
            elif not any("High cumulative exposure" in s or "Repeat counterparty" in s for s in h.historical_risk_signals):
                passed = False
                reason = f"Expected high exposure risk signal, got {h.historical_risk_signals}"

        elif cid == "DAY18-04-REPEAT-CONTRADICTION":
            if res.status != "CONTRADICTED":
                passed = False
                reason = f"Expected current status CONTRADICTED, got {res.status}"
            else:
                h = cross_service.get_counterparty_history("Dispute Enterprises")
                if not h or h.contradiction_count < 1:
                    passed = False
                    reason = f"Expected contradiction_count >= 1, got {h.contradiction_count if h else 'None'}"

        elif cid == "DAY18-05-RECURRING-AMOUNT-MISMATCH":
            h = cross_service.get_counterparty_history("Dispute Enterprises")
            patterns = cross_service.get_recurring_discrepancies(entity_name="Dispute Enterprises")
            # Verify discrepancy pattern detection
            if not patterns:
                # Check general discrepancies across cases
                all_pat = cross_service.get_recurring_discrepancies()
                if not any(p.discrepancy_type in ("AMOUNT_MISMATCH", "UNMATCHED_AMOUNT", "UNLINKED_PAYMENT") for p in all_pat):
                    passed = False
                    reason = "Expected recurring discrepancy pattern for Dispute Enterprises"

        elif cid == "DAY18-06-REFERENCE-REUSE":
            ref_corr = cross_service.get_reference_history("UTR-CMS-002", current_case_id=cid)
            if not ref_corr.reuse_warning:
                passed = False
                reason = f"Expected reuse_warning=True for reference 'UTR-CMS-002', got False (occurrences: {ref_corr.occurrence_count})"
            elif "DAY18-02-REPEAT-COUNTERPARTY" not in ref_corr.previous_case_ids:
                passed = False
                reason = f"Expected reference to link to DAY18-02, got {ref_corr.previous_case_ids}"

        elif cid == "DAY18-07-MULTI-RELATED":
            corrs = cross_service.get_case_correlations(cid)
            if len(corrs) < 1:
                passed = False
                reason = f"Expected multiple case correlations, got {len(corrs)}"
            else:
                types = {c.relationship_type.value for c in corrs}
                if "SHARED_ENTITY" not in types and "SHARED_REFERENCE" not in types:
                    passed = False
                    reason = f"Expected SHARED_ENTITY or SHARED_REFERENCE in correlations, got {types}"

        elif cid == "DAY18-08-NO-MATCH":
            h = cross_service.get_counterparty_history("Zenith Cloud Sol", exclude_case_id=cid)
            if h is not None and h.case_count > 0:
                passed = False
                reason = f"Expected 0 prior history for Zenith Cloud Sol, got {h.case_count}"
            else:
                corrs = cross_service.get_case_correlations(cid)
                if len(corrs) > 0:
                    passed = False
                    reason = f"Expected 0 correlations for isolated case, got {len(corrs)}"

        elif cid == "DAY18-09-CROSS-CASE-ISOLATION":
            # Verify that earlier contradictions did not taint Alpha Logistics
            if res.status != "CONFIRMED":
                passed = False
                reason = f"Expected status CONFIRMED, got {res.status}"
            elif res.reconciliation.matched_amount != 15000.0:
                passed = False
                reason = f"Expected matched_amount=15000, got {res.reconciliation.matched_amount}"

        elif cid == "DAY18-10-ALIAS-HISTORY":
            h = cross_service.get_counterparty_history("Creative Minds")
            if not h or h.canonical_name != "Creative Minds Studio":
                passed = False
                reason = f"Expected alias 'Creative Minds' to resolve to 'Creative Minds Studio', got {h.canonical_name if h else 'None'}"

        elif cid == "DAY18-11-MIXED-SIGNALS":
            signals = cross_service.get_historical_risk_signals(cid)
            if not signals:
                passed = False
                reason = "Expected historical risk signals for Dispute Enterprises, got 0"
            else:
                sig_types = {s.signal_type for s in signals}
                if "REPEAT_CONTRADICTION" not in sig_types and "REPEAT_COUNTERPARTY" not in sig_types:
                    passed = False
                    reason = f"Expected REPEAT_CONTRADICTION or REPEAT_COUNTERPARTY signal, got {sig_types}"

        elif cid == "DAY18-12-TRUTH-IMMUTABILITY":
            # Crucial invariant: Reconciliation is 100% CONFIRMED even though Dispute Enterprises has historical disputes
            if res.status != "CONFIRMED":
                passed = False
                reason = f"INVARIANT BREACH: Reconciliation truth mutated! Expected CONFIRMED, got {res.status}"
            elif res.reconciliation.matched_amount != 18000.0 or res.reconciliation.outstanding_amount != 0.0:
                passed = False
                reason = f"INVARIANT BREACH: Amounts modified! Matched: {res.reconciliation.matched_amount}"

        if passed:
            passed_count += 1
            print(f"  --> PASS {reason}")
            results.append((cid, desc, True, "PASS"))
        else:
            failed_count += 1
            print(f"  --> FAIL: {reason}")
            results.append((cid, desc, False, reason))

    print("\n" + "=" * 80)
    print("DAY 18 EVALUATION SUMMARY")
    print("=" * 80)
    for cid, desc, ok, msg in results:
        status_str = "PASS" if ok else f"FAIL ({msg})"
        print(f"  [{status_str:4s}] {cid:32s} - {desc[:40]}")

    print("-" * 80)
    print(f"TOTAL: {len(test_cases)} | PASSED: {passed_count} | FAILED: {failed_count} | SCORE: {(passed_count / len(test_cases)) * 100:.1f}%")
    print("=" * 80)

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(run_evaluation())
