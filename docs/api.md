# VERITY Finance Controller API Documentation

**Day 11 Milestone: Production API Layer & System Endpoints**  
*Razorpay AI Buildathon 2026 | Track: AI Finance Controller*

---

## 1. Overview & Architecture

The **VERITY API** exposes the deterministic 8-stage Finance Controller Pipeline via a high-performance, asynchronous REST interface built with **FastAPI**:

$$\text{Evidence / Payloads} \longrightarrow \text{FastAPI REST Endpoints} \longrightarrow \text{CaseProcessingService} \longrightarrow \text{FinanceControllerPipeline (8 Stages)} \longrightarrow \text{CaseResponse}$$

### 🔒 Safety Guarantees & Non-Negotiables
1. **Uncertainty Preservation**: `AMBIGUOUS`, `CONTRADICTED`, `UNMATCHED`, and `UNVERIFIABLE` statuses are never silently resolved or turned into `CONFIRMED`.
2. **Zero Hallucination**: No LLM is used in financial calculations or status assignment.
3. **Traceability**: Every response contains tamper-evident SHA-256 DAG provenance linking conclusions back to root evidence.

---

## 2. API Endpoints Reference

### System & Health Endpoints

#### `GET /health`
Returns system liveness and service status.

**Response (`200 OK`)**:
```json
{
  "status": "ok",
  "service": "verity",
  "version": "day12"
}
```

#### `GET /ready`
Returns subsystem readiness diagnostics (config validity, case store, benchmark, and pipeline status).

**Response (`200 OK`)**:
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

#### `GET /api/v1/info`
Returns application capabilities, supported modalities, and pipeline stage inventory.

**Response (`200 OK`)**:
```json
{
  "app_name": "VERITY — Financial Truth, Reconstructed",
  "version": "0.1.0-day11",
  "track": "AI Finance Controller (Razorpay AI Buildathon 2026)",
  "available_pipeline_stages": [
    "INGESTION",
    "EXTRACTION",
    "ENTITY_RESOLUTION",
    "TRANSACTION_MATCHING",
    "DEDUPLICATION",
    "CONTRADICTION_DETECTION",
    "RECONCILIATION",
    "REPORTING"
  ],
  "supported_modalities": [
    "BANK_STATEMENT (CSV)",
    "INVOICE (PDF, Text)",
    "MESSAGING_CHAT (WhatsApp, SMS)",
    "PAYMENT_SCREENSHOT (PNG, JPG)",
    "CASH_VOUCHER"
  ],
  "safety_guarantees": [
    "Zero LLM hallucination in financial math",
    "Deterministic Indian entity resolution (GSTIN, PAN, UPI, Phone)",
    "Strict uncertainty preservation (AMBIGUOUS, CONTRADICTED never falsely confirmed)",
    "Immutable SHA-256 Provenance DAG trace"
  ]
}
```

---

### Case Processing Endpoints

#### `POST /api/v1/cases`
Processes a structured case input object through the 8-stage pipeline.

**Request Body**:
```json
{
  "case_id": "CASE-2026-001",
  "evidence_items": [
    {
      "id": "E1",
      "modality": "INVOICE",
      "source_type": "ZOHO_INVOICE",
      "source_name": "inv_101.pdf",
      "raw_payload": "Invoice for INR 35,000 to Rahul Kumar"
    }
  ],
  "transactions": [
    {
      "id": "T1",
      "amount": 35000.0,
      "direction": "CREDIT",
      "bank_reference": "408219381920",
      "origin_entity_id": "ENT-001"
    }
  ],
  "entities": [
    {
      "id": "ENT-001",
      "canonical_name": "Rahul Kumar",
      "entity_type": "INDIVIDUAL",
      "pan": "ABCDE1234F"
    }
  ],
  "metadata": {
    "precomputed_claims": [
      {
        "id": "C1",
        "evidence_id": "E1",
        "claim_type": "INVOICE_ISSUED",
        "claimed_amount": 35000.0,
        "reference_id_hint": "408219381920",
        "counterparty_hint": "Rahul Kumar"
      }
    ]
  }
}
```

**Response (`200 OK`)**:
```json
{
  "case_id": "CASE-2026-001",
  "status": "CONFIRMED",
  "confidence": 1.0,
  "requires_review": false,
  "financial_summary": {
    "claimed_amount": 35000.0,
    "matched_amount": 35000.0,
    "outstanding_amount": 0.0,
    "total_reconciled_batch": 35000.0,
    "total_outstanding_batch": 0.0,
    "evidence_count": 1,
    "claims_count": 1,
    "transactions_count": 1,
    "discrepancies_count": 0
  },
  "stage_execution": [
    {
      "stage": "INGESTION",
      "status": "SUCCESS",
      "duration_ms": 0.12,
      "items_in": 1,
      "items_out": 1
    }
  ],
  "total_execution_time_ms": 1.25,
  "text_report": "============================================================\nVERITY FINANCIAL TRUTH REPORT\n..."
}
```

#### `POST /api/v1/cases/text`
Direct unstructured text / WhatsApp chat export ingestion.

**Request Body**:
```json
{
  "text": "[23/08/26, 2:30 PM] Rahul Kumar: ₹35,000 sent via UPI 408219381920",
  "source_name": "whatsapp_chat.txt"
}
```

#### `POST /api/v1/cases/files`
Multipart form upload accepting Bank CSVs, PDF invoices, and payment screenshots.

---

### Demo & Provenance Endpoints

#### `GET /api/v1/demo-cases`
Returns all 10 pre-packaged benchmark demonstration cases.

#### `POST /api/v1/demo-cases/{case_id}/run`
Executes a specific pre-packaged benchmark case.

---

### AI Finance Controller Endpoints

#### `GET /api/v1/cases/{case_id}/controller`
Returns the strongly typed `ControllerDecision` for a reconciled case, including risk classification (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `NONE`), action verdict, review requirement, and supporting domain IDs.

#### `GET /api/v1/cases/{case_id}/controller/brief`
Returns the executive `ControllerBrief` synthesizing risk summaries, financial accounting figures, active discrepancies, and prioritized action directives.

#### `POST /api/v1/cases/{case_id}/controller/explain`
Answers natural-language controller queries grounded strictly in deterministic facts.

**Request Body**:
```json
{
  "question": "Why is human review required for this case?"
}
```

**Response (`200 OK`)**:
```json
{
  "case_id": "CASE-101",
  "question": "Why is human review required for this case?",
  "answer": "Human review is required for case 'CASE-101' (Risk Level: HIGH) because the deterministic engine detected the following issues:\n• Amount mismatch: expected 20000.00, observed 18000.00",
  "grounding_ids": ["DISC-01", "CLM-01", "TXN-01"],
  "confidence": 0.98,
  "fallback_used": true
}
```

### Financial Case Portfolio & Operations Endpoints (Day 15)

#### `GET /api/v1/portfolio`
Query portfolio cases with filtering, sorting, search, and pagination.

**Query Parameters**:
- `status`: Optional filter (`NEW`, `TRIAGED`, `ASSIGNED`, `IN_REVIEW`, `WAITING_FOR_EVIDENCE`, `ESCALATED`, `RESOLVED`, `CLOSED`)
- `priority`: Optional filter (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`)
- `sla_status`: Optional filter (`ON_TRACK`, `DUE_SOON`, `OVERDUE`, `PAUSED`, `COMPLETED`)
- `reviewer_id`: Optional filter by assigned reviewer or `unassigned`
- `search`: Case ID, entity, UTR, or claim search string
- `sort_field`: Sort by `priority`, `amount_exposure`, `created_at`, `sla_due_at`, `risk_level`
- `sort_order`: `asc` or `desc`
- `page`: 1-based page index (default: 1)
- `page_size`: Bounded items per page (default: 20, max: 100)

#### `GET /api/v1/portfolio/summary`
Returns high-level portfolio KPIs: total cases, open cases, critical cases, high-risk cases, in-review cases, overdue cases, total exposure, disputed amount, and unresolved amount.

#### `GET /api/v1/portfolio/exposure`
Returns complete monetary exposure breakdowns across risk levels, operational statuses, and currency totals.

#### `GET /api/v1/portfolio/workload`
Returns active workload analytics for all assigned reviewers, including open cases, critical cases, overdue cases, exposure totals, and automated overload indicators.

#### `GET /api/v1/portfolio/cases/{case_id}`
Returns the comprehensive `CasePortfolioItem` for a single case.

#### `GET /api/v1/portfolio/cases/{case_id}/sla`
Returns the operational SLA status, deadline, elapsed hours, and remaining hours.

#### `GET /api/v1/portfolio/cases/{case_id}/priority`
Returns the deterministic `PortfolioPriorityScore`, computed priority tier, and explainable grounded reasons.

#### `POST /api/v1/portfolio/cases/{case_id}/assign`
Assigns a case to a reviewer:
```json
{
  "reviewer_id": "ctrl_alice",
  "reviewer_name": "Alice Senior Controller"
}
```

#### `POST /api/v1/portfolio/cases/{case_id}/reassign`
Reassigns an existing case to a different reviewer.

#### `POST /api/v1/portfolio/cases/{case_id}/unassign`
Removes the active reviewer assignment.

#### `GET /api/v1/portfolio/review-queue`
Returns all cases requiring active human investigation.

#### `GET /api/v1/portfolio/overdue`
Returns all open cases that have exceeded their SLA window.

#### `GET /api/v1/portfolio/high-risk`
Returns all cases categorized as `CRITICAL` or `HIGH` risk.

---

### Storage & Infrastructure Endpoints (Day 16)

#### `GET /api/v1/storage/health`
Returns live database engine connectivity, pool utilization, and storage diagnostics.

**Response (`200 OK`)**:
```json
{
  "status": "HEALTHY",
  "dialect": "sqlite",
  "total_cases_stored": 12,
  "total_audit_events": 48,
  "tables_count": 18
}
```

#### `GET /api/v1/storage/stats`
Returns row counts across all 18 persistent database tables.

#### `GET /api/v1/cases/{case_id}/persistence`
Returns presence and persistence status for all artifacts associated with a case.

#### `GET /api/v1/cases/{case_id}/audit/integrity`
Cryptographically verifies the SHA-256 hash-chain integrity of audit events for a case.

**Response (`200 OK`)**:
```json
{
  "case_id": "CASE-2026-001",
  "is_valid": true,
  "total_events": 4,
  "errors": [],
  "latest_state_hash": "a1b2c3d4..."
}
```


---

### Cross-Case Intelligence & Counterparty Memory Endpoints (Day 18)

#### `GET /api/v1/entities/{canonical_name_or_id}/history`
Returns counterparty historical profile across all cases: lifetime volume, disputed amounts, unresolved exposure, contradiction frequency, and risk alerts.

**Response (`200 OK`)**:
```json
{
  "entity_id": "ENT-CMS-1",
  "canonical_name": "Creative Minds Studio",
  "aliases": ["Creative Minds"],
  "gstin": "27AABCC1234D1Z5",
  "case_count": 3,
  "total_exposure": 125000.0,
  "disputed_exposure": 0.0,
  "unresolved_exposure": 0.0,
  "contradiction_count": 0,
  "previous_case_ids": ["DAY18-02-REPEAT-COUNTERPARTY", "DAY18-03-HIGH-EXPOSURE"],
  "historical_risk_signals": []
}
```

#### `GET /api/v1/entities/{canonical_name_or_id}/exposure`
Returns monetary exposure breakdown across cases for the given entity.

#### `GET /api/v1/references/{reference_id}/history`
Detects duplicate bank reference / UTR reuse across distinct cases.

**Response (`200 OK`)**:
```json
{
  "reference_id": "UTR-CMS-002",
  "current_case_id": null,
  "previous_case_ids": ["DAY18-02-REPEAT-COUNTERPARTY", "DAY18-06-REFERENCE-REUSE"],
  "transaction_ids": ["TXN-D18-02-1"],
  "claim_ids": ["CLM-D18-02-1", "CLM-D18-06-1"],
  "occurrence_count": 2,
  "reuse_warning": true
}
```

#### `GET /api/v1/cases/{case_id}/correlations`
Returns deterministic machine-verifiable relationships (`SHARED_ENTITY`, `SHARED_REFERENCE`, `RECURRING_DISCREPANCY`, `SHARED_EVIDENCE_HASH`) linking the case to historical cases.

#### `GET /api/v1/cases/{case_id}/historical-signals`
Surfaces explainable historical risk warnings for the AI Finance Controller without altering deterministic financial truth.

#### `GET /api/v1/cases/{case_id}/intelligence-profile`
Returns unified dossier containing all counterparty memory, reference checks, recurring discrepancy patterns, correlations, and historical alerts for the given case.

---

### Proactive Remediation & Actions Endpoints (Day 19)

#### `POST /api/v1/cases/{case_id}/actions/propose`
Proposes a fact-grounded remediation action (`VENDOR_DISPUTE_NOTICE`, `PAYMENT_FOLLOWUP_DRAFT`, `MISSING_EVIDENCE_REQUEST`, or `DRAFT_JOURNAL_VOUCHER`).

**Request Body**:
```json
{
  "action_type": "VENDOR_DISPUTE_NOTICE",
  "channel": "EMAIL",
  "recipient_contact": "finance@vendor.com"
}
```

#### `GET /api/v1/cases/{case_id}/actions`
Lists all proposed and reviewed remediation action items for a case.

#### `POST /api/v1/cases/{case_id}/actions/{action_id}/approve`
Explicit human approval of a proposed action. Emits an immutable `ACTION_APPROVED` event into the SHA-256 audit hash chain.

**Request Body**:
```json
{
  "reviewer_id": "lead_controller_1",
  "notes": "Approved formal notice to counterparty"
}
```

#### `POST /api/v1/cases/{case_id}/actions/{action_id}/reject`
Explicit human rejection of a proposed action with controller reason. Emits `ACTION_REJECTED` into the SHA-256 audit hash chain.

**Request Body**:
```json
{
  "reviewer_id": "lead_controller_1",
  "reason": "Settlement already agreed by phone",
  "notes": "No dispute letter needed"
}
```

#### `GET /api/v1/cases/{case_id}/journal-voucher`
Returns the deterministic balanced double-entry Draft Journal Voucher derived directly from authoritative reconciliation results. Enforces `Total Debits == Total Credits` and flags `requires_account_mapping: true` if using placeholder COA.

#### `POST /api/v1/cases/{case_id}/journal-voucher/export`
Exports the balanced draft journal voucher (JSON) and records an immutable `JOURNAL_EXPORTED` event in the audit store.

---

## 3. Starting the API Server

```bash
# Run FastAPI server with Uvicorn
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Interactive Swagger API docs are accessible at: `http://localhost:8000/docs`


