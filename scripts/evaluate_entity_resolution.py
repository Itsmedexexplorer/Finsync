"""Evaluation runner for VERITY Entity Resolution subsystem."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.domain.entity import Entity
from backend.entity_resolution.registry import EntityRegistry
from backend.entity_resolution.result import EntityResolutionStatus
from backend.entity_resolution.service import EntityResolutionService


def evaluate_entity_resolution() -> bool:
    print("=" * 70)
    print("VERITY ENTITY RESOLUTION EVALUATION & FALSE-MERGE AUDIT")
    print("=" * 70)

    fixtures_path = root_dir / "data" / "samples" / "day4" / "entity_resolution_cases.json"
    if not fixtures_path.exists():
        print(f"[ERROR] Fixtures file not found: {fixtures_path}")
        return False

    with open(fixtures_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Initialize Registry & Service
    registry = EntityRegistry()
    for ent_dict in data.get("registered_entities", []):
        ent = Entity.model_validate(ent_dict)
        registry.register_entity(ent)

    service = EntityResolutionService(registry=registry)
    print(f"Loaded {len(registry.list_all())} registered entities into registry.")

    # 2. Run Test Cases
    test_cases = data.get("test_cases", [])
    print(f"Running {len(test_cases)} evaluation scenarios...\n")

    passed_count = 0
    false_merges = 0
    status_breakdown = {s.value: 0 for s in EntityResolutionStatus}

    for tc in test_cases:
        cid = tc["case_id"]
        desc = tc["description"]
        query = tc["query"]
        expected_status = tc["expected_status"]
        expected_ent_id = tc["expected_entity_id"]

        result = service.resolve_query(
            query_name=query.get("query_name"),
            query_handle=query.get("query_handle"),
            query_phone=query.get("query_phone"),
            query_tax_id=query.get("query_tax_id"),
            claim_id=cid,
        )

        status_breakdown[result.status.value] += 1
        
        # Check false merge: resolved to an entity when expected was None or a different entity
        is_false_merge = False
        if expected_ent_id is None and result.selected_entity_id is not None:
            is_false_merge = True
        elif expected_ent_id and result.selected_entity_id and result.selected_entity_id != expected_ent_id:
            is_false_merge = True

        if is_false_merge:
            false_merges += 1
            print(f"[CRITICAL FAIL - FALSE MERGE] {cid}: Expected {expected_ent_id}, got {result.selected_entity_id}")
            print(f"  Explanation: {result.explanation}")
            continue

        # Check status match
        if result.status.value == expected_status and result.selected_entity_id == expected_ent_id:
            passed_count += 1
            print(f"  [PASS] {cid:<32} -> {result.status.value:<12} (Entity: {result.selected_entity_id or 'None'})")
        else:
            print(f"  [FAIL] {cid:<32} -> Got {result.status.value} (Expected {expected_status})")
            print(f"         Explanation: {result.explanation}")

    print("\n" + "-" * 70)
    print("EVALUATION METRICS & BREAKDOWN")
    print("-" * 70)
    print(f"Total Scenarios Evaluated   : {len(test_cases)}")
    print(f"Scenarios Passed            : {passed_count} / {len(test_cases)} ({passed_count/len(test_cases)*100:.1f}%)")
    print(f"False Merges Detected       : {false_merges} (TARGET: 0)")
    print(f"False Merge Rate            : {false_merges/len(test_cases)*100:.1f}%")
    print("\nResolution Status Distribution:")
    for stat, count in sorted(status_breakdown.items()):
        print(f"  * {stat:<15}: {count:>2} cases")

    success = (passed_count == len(test_cases)) and (false_merges == 0)
    print("=" * 70)
    if success:
        print("VERITY ENTITY RESOLUTION VERIFICATION SUCCESSFUL (100% Correct, 0% False Merges)")
    else:
        print("[FAIL] Entity resolution verification failed.")
    print("=" * 70)
    return success


if __name__ == "__main__":
    ok = evaluate_entity_resolution()
    sys.exit(0 if ok else 1)
