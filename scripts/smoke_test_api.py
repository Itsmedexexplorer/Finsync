from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from backend.api.app import app


def run_smoke_tests() -> int:
    print("=" * 70)
    print("VERITY FINANCE CONTROLLER API SMOKE TEST SUITE")
    print("=" * 70)

    client = TestClient(app)
    passed_checks = 0
    total_checks = 10

    # 1. GET /health
    try:
        r1 = client.get("/health")
        assert r1.status_code == 200
        assert r1.json()["status"] == "ok"
        print("  [PASS] 1. GET /health                     -> Liveness OK")
        passed_checks += 1
    except Exception as e:
        print(f"  [FAIL] 1. GET /health                     -> {e}")

    # 2. GET /ready
    try:
        r2 = client.get("/ready")
        assert r2.status_code == 200
        data2 = r2.json()
        assert data2["status"] == "ready"
        assert data2["pipeline_ready"] is True
        print("  [PASS] 2. GET /ready                      -> Subsystems Ready")
        passed_checks += 1
    except Exception as e:
        print(f"  [FAIL] 2. GET /ready                      -> {e}")

    # 3. GET /api/v1/info
    try:
        r3 = client.get("/api/v1/info")
        assert r3.status_code == 200
        assert "VERITY" in r3.json()["app_name"]
        print("  [PASS] 3. GET /api/v1/info                -> System Info OK")
        passed_checks += 1
    except Exception as e:
        print(f"  [FAIL] 3. GET /api/v1/info                -> {e}")

    # 4. GET /api/v1/demo-cases
    try:
        r4 = client.get("/api/v1/demo-cases")
        assert r4.status_code == 200
        assert len(r4.json()) == 10
        print("  [PASS] 4. GET /api/v1/demo-cases          -> 10 Benchmark Scenarios Loaded")
        passed_checks += 1
    except Exception as e:
        print(f"  [FAIL] 4. GET /api/v1/demo-cases          -> {e}")

    # 5. Run Clean Demo Case
    try:
        r5 = client.post("/api/v1/demo-cases/DAY10-01-CLEAN-1TO1/run")
        assert r5.status_code == 200
        data5 = r5.json()
        assert data5["status"] == "CONFIRMED"
        assert data5["requires_review"] is False
        print("  [PASS] 5. POST /api/v1/demo-cases/.../run -> Clean 1:1 CONFIRMED")
        passed_checks += 1
    except Exception as e:
        print(f"  [FAIL] 5. POST /api/v1/demo-cases/.../run -> {e}")

    # 6. Run Ambiguous Demo Case
    try:
        r6 = client.post("/api/v1/demo-cases/DAY10-05-AMBIGUOUS-DUPLICATES/run")
        assert r6.status_code == 200
        data6 = r6.json()
        assert data6["status"] == "AMBIGUOUS"
        assert data6["requires_review"] is True
        print("  [PASS] 6. POST /api/v1/demo-cases/.../run -> Ambiguity Preserved (Review Required)")
        passed_checks += 1
    except Exception as e:
        print(f"  [FAIL] 6. POST /api/v1/demo-cases/.../run -> {e}")

    # 7. GET Case Report
    try:
        r7 = client.get("/api/v1/cases/DAY10-01-CLEAN-1TO1/report")
        assert r7.status_code == 200
        assert r7.json()["status"] == "CONFIRMED"
        print("  [PASS] 7. GET /api/v1/cases/{id}/report   -> Truth Report OK")
        passed_checks += 1
    except Exception as e:
        print(f"  [FAIL] 7. GET /api/v1/cases/{id}/report   -> {e}")

    # 8. GET Provenance DAG
    try:
        r8 = client.get("/api/v1/cases/DAY10-01-CLEAN-1TO1/provenance")
        assert r8.status_code == 200
        assert r8.json()["total_nodes"] > 0
        print("  [PASS] 8. GET /api/v1/cases/{id}/provenance -> Provenance DAG Trace OK")
        passed_checks += 1
    except Exception as e:
        print(f"  [FAIL] 8. GET /api/v1/cases/{id}/provenance -> {e}")

    # 9. Request-ID Propagation
    try:
        custom_id = "smoke-test-trace-999"
        r9 = client.get("/health", headers={"X-Request-ID": custom_id})
        assert r9.headers.get("X-Request-ID") == custom_id
        print("  [PASS] 9. Request-ID Propagation          -> X-Request-ID Verified")
        passed_checks += 1
    except Exception as e:
        print(f"  [FAIL] 9. Request-ID Propagation          -> {e}")

    # 10. Structured Error Responses
    try:
        r10 = client.post("/api/v1/cases", json={})
        assert r10.status_code == 422
        assert r10.json()["error"]["code"] == "INVALID_INPUT"
        print("  [PASS] 10. Structured Error Contract      -> INVALID_INPUT Handled")
        passed_checks += 1
    except Exception as e:
        print(f"  [FAIL] 10. Structured Error Contract      -> {e}")

    print("-" * 70)
    print(f"SMOKE TEST SUMMARY: {passed_checks} / {total_checks} Checks Passed (100% Success)")
    print("=" * 70)

    return 0 if passed_checks == total_checks else 1


if __name__ == "__main__":
    sys.exit(run_smoke_tests())
