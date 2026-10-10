# VERITY Reliability & Resilience Engineering

**Day 12 Milestone: Production Hardening & System Reliability**  
*Razorpay AI Buildathon 2026 | Track: AI Finance Controller*

---

## 1. Reliability Overview

VERITY is engineered for predictable, deterministic, and resilient execution. It operates without external runtime dependencies (no third-party cloud LLM API lock-in for decision math), ensuring 100% offline operational capability.

---

## 2. Health & Readiness Diagnostics

### Basic Liveness: `GET /health`
Validates that the HTTP server process is running and responding.
```json
{
  "status": "ok",
  "service": "verity",
  "version": "day12"
}
```

### Comprehensive Readiness: `GET /ready`
Validates that all internal subsystems are operational before routing financial traffic:
```json
{
  "status": "ready",
  "service": "verity",
  "environment": "development",
  "config_valid": true,
  "case_store_ready": true,
  "benchmark_available": true,
  "pipeline_ready": true,
  "active_cases_in_memory": 10,
  "version": "day12"
}
```

---

## 3. In-Memory Demo Case Store Hardening

The lightweight session store (`InMemoryCaseStore` in `backend/api/dependencies.py`) provides:
- **Thread Safety**: Protected with `threading.Lock` across concurrent async requests.
- **FIFO Eviction & Capacity Bounds**: Configured via `VERITY_MAX_CASES_IN_MEMORY` (default 1000). When capacity is reached, the oldest entries are evicted gracefully to prevent memory leaks.
- **Preloaded Benchmark Fixtures**: Day 10 test fixtures are loaded at startup for instantaneous UI demo execution.

---

## 4. Frontend Resilience

The interactive dashboard (`frontend/app.js` and `frontend/index.html`) includes defensive client-side protections:
- **Client-Side File Pre-validation**: Files exceeding `15 MB` or having invalid extensions are caught client-side with immediate visual warnings.
- **Structured Error Banners**: API error payloads (`ErrorResponse`) are rendered into contextual banners displaying error codes and messages.
- **Heartbeat & Reconnection**: Periodic polling of `/ready` updates the top status badge dynamically (`Engine Ready` vs `API Disconnected`).
- **Loading & State Isolation**: Input buttons disable during analysis with spinner animations to prevent duplicate submissions.

---

## 5. Automated Verification & Smoke Testing

A dedicated end-to-end smoke test script (`scripts/smoke_test_api.py`) verifies all 10 operational invariants:
```bash
python scripts/smoke_test_api.py
```
- Liveness check (`/health`)
- Readiness check (`/ready`)
- System info metadata (`/api/v1/info`)
- Demo cases listing (`/api/v1/demo-cases`)
- Clean case execution (`CONFIRMED`)
- Ambiguous case execution (`AMBIGUOUS`, review required)
- Truth report retrieval (`/cases/{id}/report`)
- Cryptographic provenance DAG trace (`/cases/{id}/provenance`)
- Request-ID header propagation (`X-Request-ID`)
- Structured error handling (`INVALID_INPUT`)

---

## 6. Persistent Storage & Crash Recovery (Day 16)

VERITY incorporates durable persistence infrastructure:
- **Thread-Safe Connection Pooling**: Reusable connection pool with `sqlite3` driver, foreign keys enforced (`PRAGMA foreign_keys = ON`), WAL journal mode, and configurable busy timeouts.
- **Atomic Transactions & Savepoints**: Multi-table case persistence is fully transactional. Any error during evidence, claim, or report persistence triggers an immediate rollback to prevent corrupted or partial records.
- **Cryptographic Audit Integrity**: SHA-256 hash chaining detects database corruption or tampering across restarts.
- **Complete Cold-Restart Recovery**: All cases, review history, reviewer assignments, and portfolio SLA states are recovered seamlessly after server restart.

