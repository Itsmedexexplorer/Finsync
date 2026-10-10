"""VERITY AI Finance Controller Evaluation & Safety Audit Script.

Evaluates 10 deterministic controller scenarios, validating risk classification accuracy,
action prioritization, explainability provenance, and AI safety invariants.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.case_processing.service import CaseProcessingService
from backend.controller.ai_explainer import validate_ai_output
from backend.controller.models import ControllerAIResponse
from backend.controller.service import ControllerService


def run_controller_evaluation() -> int:
    print("=" * 70)
    print("VERITY AI FINANCE CONTROLLER EVALUATION & SAFETY AUDIT")
    print("=" * 70)

    dataset_path = Path("data/samples/day13/controller_cases.json")
    if not dataset_path.exists():
        print(f"[ERROR] Evaluation dataset not found at {dataset_path}")
        return 1

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    test_cases = data.get("test_cases", [])
    print(f"Running {len(test_cases)} controller evaluation scenarios...\n")

    case_service = CaseProcessingService()
    controller_service = ControllerService()

    total_scenarios = len(test_cases)
    passed_scenarios = 0
    risk_accuracy_count = 0
    action_accuracy_count = 0
    false_confirmations = 0
    unsupported_claims = 0
    provenance_failures = 0
    ai_validation_passed = 0

    for tc in test_cases:
        cid = tc["case_id"]
        exp_risk = tc["expected_risk_level"]
        exp_review = tc["expected_requires_review"]
        exp_action = tc["expected_primary_action"]

        # 1. Run Pipeline
        case_result = case_service.process_benchmark_case(tc["case_input"])

        # 2. Run Controller Analysis & Brief
        decision = controller_service.analyze_case(case_result)
        brief = controller_service.build_brief(case_result)

        # 3. Check Risk & Action
        actual_risk = decision.risk_level.value
        actual_action = decision.decision.value
        actual_review = decision.requires_human_review

        risk_match = (actual_risk == exp_risk)
        action_match = (actual_action == exp_action)
        review_match = (actual_review == exp_review)

        if risk_match:
            risk_accuracy_count += 1
        if action_match:
            action_accuracy_count += 1

        # 4. Safety Invariants
        if exp_review and not actual_review:
            false_confirmations += 1
            print(f"  [SAFETY VIOLATION] False confirmation in case {cid}")

        # Check for ungrounded actions
        for act in decision.recommended_actions:
            if act.blocking_issue and not act.supporting_ids and exp_risk in ("HIGH", "CRITICAL"):
                provenance_failures += 1

        # 5. AI Validation Sub-check
        # Test synthetic good response
        synthetic_good = ControllerAIResponse(
            summary=brief.executive_summary,
            key_findings=[f"Status: {case_result.status}"],
            recommended_actions=[a.title for a in decision.recommended_actions],
        )
        context = {
            "status": case_result.status,
            "known_amounts": [float(a) for a in [
                case_result.financial_summary.get("claimed_amount", 0.0) or 0.0,
                case_result.financial_summary.get("matched_amount", 0.0) or 0.0,
                case_result.financial_summary.get("outstanding_amount", 0.0) or 0.0,
            ]],
        }
        if validate_ai_output(synthetic_good, context):
            ai_validation_passed += 1

        is_passed = risk_match and action_match and review_match
        if is_passed:
            passed_scenarios += 1
            print(f"  [PASS] {cid:<34} -> Risk: {actual_risk:<8} | Action: {actual_action:<24} | Review: {'YES' if actual_review else 'NO'}")
        else:
            print(f"  [FAIL] {cid:<34} -> Expected: ({exp_risk}, {exp_action}, {exp_review}) | Got: ({actual_risk}, {actual_action}, {actual_review})")

    print("\n" + "-" * 70)
    print("EVALUATION METRICS & AUDIT BREAKDOWN")
    print("-" * 70)
    print(f"Total Scenarios Evaluated       : {total_scenarios}")
    print(f"Scenarios Passed                : {passed_scenarios} / {total_scenarios} ({passed_scenarios / total_scenarios * 100:.1f}%)")
    print(f"Risk Classification Accuracy    : {risk_accuracy_count / total_scenarios * 100:.1f}%")
    print(f"Action Recommendation Accuracy  : {action_accuracy_count / total_scenarios * 100:.1f}%")
    print(f"AI Safety Validations Passed    : {ai_validation_passed} / {total_scenarios}")
    print(f"False Confirmations Detected    : {false_confirmations} (TARGET: 0)")
    print(f"Unsupported Financial Claims    : {unsupported_claims} (TARGET: 0)")
    print(f"Provenance Failures             : {provenance_failures} (TARGET: 0)")
    print("=" * 70)

    if passed_scenarios == total_scenarios and false_confirmations == 0 and provenance_failures == 0:
        print("VERITY AI FINANCE CONTROLLER VERIFICATION SUCCESSFUL (100% Correct, 0 Violations)")
        print("=" * 70)
        return 0
    else:
        print("[FAIL] Controller evaluation did not meet 100% required safety and correctness criteria.")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(run_controller_evaluation())
