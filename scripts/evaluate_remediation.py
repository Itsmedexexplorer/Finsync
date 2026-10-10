"""VERITY Day 19 Evaluator: Proactive Controller Actions & Human-in-the-Loop Remediation.

Evaluates 12 scenarios:
1. Balanced Draft Journal Voucher Generation (CONFIRMED)
2. Partial Allocation Draft Journal Voucher (PARTIAL)
3. Fact-Grounded Vendor Dispute Notice Generation (CONTRADICTED)
4. Fact-Grounded Payment Follow-Up Notice (PARTIAL)
5. Missing Evidence Request Draft (UNVERIFIABLE)
6. Human Approval Workflow & Audit Trail Recording
7. Human Rejection Workflow with Controller Reason
8. Configurable Chart-of-Accounts (COA) Mapping
9. Strict Grounding Validation (Pass)
10. Strict Grounding Validation (Reject on Tampering)
11. Double-Entry Debits == Credits Mathematical Balance Invariant
12. Deterministic Financial Truth Immutability under Remediation Actions
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.case_processing.service import CaseProcessingService
from backend.controller.remediation.generator import RemediationDraftGenerator
from backend.controller.remediation.journal_engine import DraftJournalEngine
from backend.controller.remediation.models import (
    ActionApprovalStatus,
    DraftJournalVoucher,
    RemediationActionType,
    RemediationNoticeDraft,
)
from backend.controller.remediation.service import RemediationActionService
from backend.controller.remediation.validator import RemediationValidator
from backend.storage.config import StorageSettings
from backend.storage.database import DatabaseEngine
from backend.storage.service import StorageService


def run_evaluation() -> int:
    print("=" * 80)
    print("VERITY DAY 19 EVALUATOR: PROACTIVE REMEDIATION & HUMAN-IN-THE-LOOP ACTIONS")
    print("=" * 80)

    fixtures_path = Path("data/samples/day19/remediation_cases.json")
    if not fixtures_path.exists():
        print(f"ERROR: Fixture file {fixtures_path} does not exist.")
        return 1

    with open(fixtures_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    print(f"Loaded {len(cases)} evaluation test cases.\n")

    # Set up clean temporary database
    temp_dir = tempfile.mkdtemp(prefix="verity_eval_d19_")
    db_path = os.path.join(temp_dir, "eval_d19.db")
    settings = StorageSettings(database_url=f"sqlite:///{db_path}", pool_size=1, timeout_seconds=30.0)
    engine = DatabaseEngine(settings=settings)
    engine.initialize()

    case_service = CaseProcessingService()
    storage_service = StorageService(engine=engine)
    remediation_service = RemediationActionService(engine=engine)

    passed_count = 0
    failed_count = 0
    results_summary = []

    print("--- Sequential Case Processing & Remediation Workflow ---")

    for idx, tc in enumerate(cases, start=1):
        cid = tc["case_id"]
        scenario = tc.get("scenario_type", "UNKNOWN")
        desc = tc.get("description", "")

        print(f"\n[{idx}/{len(cases)}] Evaluating Case: {cid}")
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

        # 2. Persist Case into SQLite storage
        storage_service.process_and_persist_case(
            case_result=res,
            raw_evidence_list=tc.get("evidence", []),
            raw_claims_list=tc.get("claims", []),
            raw_entities_list=tc.get("entities", []),
            raw_transactions_list=tc.get("transactions", []),
        )

        case_passed = True
        fail_reason = ""

        # 3. Scenario-specific remediation checks
        if scenario == "CLEAN_CONFIRMED_JOURNAL_VOUCHER":
            voucher = remediation_service.build_draft_journal_voucher(cid)
            if not voucher.is_balanced or abs(voucher.total_debits - 45000.0) > 0.01:
                case_passed = False
                fail_reason = f"Expected balanced voucher of INR 45,000, got DR: {voucher.total_debits}, CR: {voucher.total_credits}"
            if not voucher.requires_account_mapping:
                case_passed = False
                fail_reason = "Expected requires_account_mapping=True for unconfigured standard COA"

        elif scenario == "PARTIAL_SETTLEMENT_JOURNAL_VOUCHER":
            voucher = remediation_service.build_draft_journal_voucher(cid)
            if not voucher.is_balanced or abs(voucher.total_debits - 50000.0) > 0.01:
                case_passed = False
                fail_reason = f"Expected balanced partial voucher of INR 50,000, got DR: {voucher.total_debits}, CR: {voucher.total_credits}"
            if len(voucher.lines) < 3:
                case_passed = False
                fail_reason = f"Expected 3 double-entry lines for partial allocation, got {len(voucher.lines)}"

        elif scenario == "GROUNDED_VENDOR_DISPUTE_NOTICE":
            action = remediation_service.propose_dispute_notice(cid)
            draft = action.notice_draft
            if not draft or draft.action_type != RemediationActionType.VENDOR_DISPUTE_NOTICE:
                case_passed = False
                fail_reason = "Failed to propose vendor dispute notice"
            elif abs((draft.stated_disputed_amount or 0.0) - 20000.0) > 0.01:
                case_passed = False
                fail_reason = f"Expected disputed shortfall of INR 20,000, got {draft.stated_disputed_amount}"

        elif scenario == "GROUNDED_PAYMENT_FOLLOWUP":
            action = remediation_service.propose_payment_followup(cid)
            draft = action.notice_draft
            if not draft or draft.action_type != RemediationActionType.PAYMENT_FOLLOWUP_DRAFT:
                case_passed = False
                fail_reason = "Failed to propose payment follow-up"
            elif abs((draft.stated_disputed_amount or 0.0) - 10000.0) > 0.01:
                case_passed = False
                fail_reason = f"Expected outstanding balance of INR 10,000, got {draft.stated_disputed_amount}"

        elif scenario == "MISSING_EVIDENCE_REQUEST":
            action = remediation_service.propose_missing_evidence_request(cid)
            draft = action.notice_draft
            if not draft or draft.action_type != RemediationActionType.MISSING_EVIDENCE_REQUEST:
                case_passed = False
                fail_reason = "Failed to propose missing evidence request"

        elif scenario == "HUMAN_APPROVAL_WORKFLOW":
            action = remediation_service.propose_dispute_notice(cid)
            if action.approval_status != ActionApprovalStatus.PENDING_APPROVAL:
                case_passed = False
                fail_reason = "Expected initial action status PENDING_APPROVAL"
            else:
                approved = remediation_service.approve_action(action.action_id, reviewer_id="lead_controller")
                if approved.approval_status != ActionApprovalStatus.APPROVED or approved.approved_by != "lead_controller":
                    case_passed = False
                    fail_reason = "Action failed to transition to APPROVED"

        elif scenario == "HUMAN_REJECTION_WORKFLOW":
            action = remediation_service.propose_payment_followup(cid)
            rejected = remediation_service.reject_action(
                action.action_id,
                reviewer_id="lead_controller",
                rejection_reason="Vendor already contacted via phone",
            )
            if rejected.approval_status != ActionApprovalStatus.REJECTED or "phone" not in (rejected.rejection_reason or ""):
                case_passed = False
                fail_reason = "Action failed to transition to REJECTED with reason"

        elif scenario == "CUSTOM_COA_MAPPING":
            custom_coa = tc.get("custom_coa")
            voucher = remediation_service.build_draft_journal_voucher(cid, custom_coa_mapping=custom_coa)
            if voucher.requires_account_mapping is not False:
                case_passed = False
                fail_reason = "Expected requires_account_mapping=False for custom configured COA"
            dr_codes = {l.account_code for l in voucher.lines if l.debit_amount > 0}
            if "GL-2020" not in dr_codes:
                case_passed = False
                fail_reason = f"Expected custom DR code GL-2020, got {dr_codes}"

        elif scenario == "GROUNDING_VALIDATION_PASS":
            action = remediation_service.propose_payment_followup(cid)
            is_valid, errors = RemediationValidator.validate_notice_grounding(action.notice_draft, res.reconciliation, res.report)
            if not is_valid:
                case_passed = False
                fail_reason = f"Grounded notice failed validation unexpectedly: {errors}"

        elif scenario == "GROUNDING_VALIDATION_REJECT":
            action = remediation_service.propose_dispute_notice(cid)
            # Intentionally tamper with amount to test rejection
            tampered_draft = action.notice_draft.model_copy(update={"stated_expected_amount": 999999.99})
            is_valid, errors = RemediationValidator.validate_notice_grounding(tampered_draft, res.reconciliation, res.report)
            if is_valid or not errors:
                case_passed = False
                fail_reason = "Validator failed to catch tampered/hallucinated amount"

        elif scenario == "DOUBLE_ENTRY_BALANCE_CHECK":
            voucher = remediation_service.build_draft_journal_voucher(cid)
            if not voucher.is_balanced or abs(voucher.total_debits - voucher.total_credits) > 0.001:
                case_passed = False
                fail_reason = f"Double-entry imbalance detected: DR {voucher.total_debits} != CR {voucher.total_credits}"

        elif scenario == "FINANCIAL_TRUTH_IMMUTABILITY":
            initial_status = res.status
            initial_matched = res.reconciliation.matched_amount
            # Run proposals and approvals
            act1 = remediation_service.propose_dispute_notice(cid)
            remediation_service.approve_action(act1.action_id)
            act2 = remediation_service.propose_journal_voucher_action(cid)
            remediation_service.reject_action(act2.action_id, rejection_reason="Test")

            # Check that case reconciliation result in DB is 100% untouched
            recon, report = remediation_service._get_case_truth(cid)
            if recon.status.value != initial_status or recon.matched_amount != initial_matched:
                case_passed = False
                fail_reason = f"Reconciliation truth was mutated: Status {recon.status.value} vs {initial_status}"

        if case_passed:
            print(f"  --> PASS")
            passed_count += 1
            results_summary.append((cid, "PASS", desc))
        else:
            print(f"  --> FAIL: {fail_reason}")
            failed_count += 1
            results_summary.append((cid, f"FAIL ({fail_reason})", desc))

    engine.shutdown()

    # Print summary table
    print("\n" + "=" * 80)
    print("DAY 19 EVALUATION SUMMARY")
    print("=" * 80)
    for cid, status, desc in results_summary:
        print(f"  [{status[:30]}] {cid:<30} - {desc[:40]}")

    print("-" * 80)
    score_pct = (passed_count / len(cases)) * 100
    print(f"TOTAL: {len(cases)} | PASSED: {passed_count} | FAILED: {failed_count} | SCORE: {score_pct:.1f}%")
    print("=" * 80 + "\n")

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(run_evaluation())
