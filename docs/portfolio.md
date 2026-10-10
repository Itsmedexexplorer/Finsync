# VERITY Financial Case Portfolio & Operations Intelligence

**Day 15 Milestone: Financial Case Portfolio & Operations Intelligence Layer**  
*Razorpay AI Buildathon 2026 | Track: AI Finance Controller*

---

## 1. Core Architectural Overview

The **VERITY Case Portfolio & Operations Subsystem** provides a bird's-eye management and operational intelligence console above the underlying deterministic financial truth core.

$$\textbf{CORE INVARIANTS:}$$
$$\textbf{1. PORTFOLIO INTELLIGENCE MUST NEVER MODIFY FINANCIAL TRUTH.}$$
$$\textbf{2. OPERATIONAL STATUS } \neq \textbf{ DETERMINISTIC FINANCIAL TRUTH.}$$
$$\textbf{3. ZERO DOUBLE-COUNTING OF MONETARY EXPOSURE.}$$

```
                ┌─────────────────────────────────────────────────────────────┐
                │                 DETERMINISTIC PIPELINE CORE                 │
                │                                                             │
                │  Evidence ──▶ Claims ──▶ Entity Resolution ──▶ Matching     │
                │        ──▶ Deduplication ──▶ Contradictions ──▶ Recon       │
                │        ──▶ Provenance DAG & Accounting Invariants           │
                └──────────────────────────────┬──────────────────────────────┘
                                               │
                                               ▼
                ┌─────────────────────────────────────────────────────────────┐
                │                FINANCE CONTROLLER LAYER                     │
                │                                                             │
                │  • Risk Classification & Decision Intelligence              │
                │  • Prioritized Action Directives                            │
                │  • Evidence-Grounded Natural-Language Brief                 │
                └──────────────────────────────┬──────────────────────────────┘
                                               │
                                               ▼
                ┌─────────────────────────────────────────────────────────────┐
                │             HUMAN REVIEW & AUDIT WORKFLOW (DAY 14)          │
                │                                                             │
                │  • Finite State Workflow Machine                            │
                │  • Append-Only Review Notes & Evidence Inspection Tracking  │
                │  • Cryptographic SHA-256 Audit Hash Chaining                │
                └──────────────────────────────┬──────────────────────────────┘
                                               │
                                               ▼
                ┌─────────────────────────────────────────────────────────────┐
                │     FINANCIAL CASE PORTFOLIO & OPERATIONS (DAY 15)          │
                │                                                             │
                │  • Portfolio Aggregation Engine (Zero Double-Counting)      │
                │  • SLA & Case Aging Engine (On Track / Due Soon / Overdue)  │
                │  • Case Assignment, Workload & Overload Balancing           │
                │  • Multi-Factor Deterministic Prioritization Scoring        │
                │  • Full-Text Search, Filtering, Sorting & Pagination        │
                └─────────────────────────────────────────────────────────────┘
```

---

## 2. Key Operational Concepts

### 1. Operational vs Deterministic Status Separation
- `CaseProcessingResult.status` (`CONFIRMED`, `PARTIALLY_SETTLED`, `CONTRADICTED`, `AMBIGUOUS`, `UNVERIFIABLE`, `UNMATCHED`) represents mathematical truth computed from evidence.
- `CasePortfolioItem.portfolio_status` (`NEW`, `TRIAGED`, `ASSIGNED`, `IN_REVIEW`, `WAITING_FOR_EVIDENCE`, `ESCALATED`, `RESOLVED`, `CLOSED`) represents the workflow stage of the case investigation.
- Closing or resolving an operational case does **not** change its underlying deterministic status.

### 2. SLA & Aging Policy
- **CRITICAL Risk**: 4-hour SLA window
- **HIGH Risk**: 24-hour SLA window
- **MEDIUM Risk**: 72-hour (3-day) SLA window
- **LOW Risk**: 168-hour (7-day) SLA window
- **DUE_SOON**: Triggered when remaining duration is $\le 20\%$ of the window.
- **OVERDUE**: Triggered when deadline has passed.

### 3. Reviewer Assignment & Capacity Monitoring
- Assigns cases to individual controllers (`ctrl_alice`, `ctrl_bob`, etc.).
- Calculates total assigned cases, open cases, critical cases, overdue cases, and active exposure.
- Flags **OVERLOADED** reviewers when:
  - Critical cases $> 5$
  - Open cases $> 20$
  - Overdue cases $> 5$

---

## 3. REST API Reference

- `GET /api/v1/portfolio` — Filtered, sorted, and paginated portfolio case query.
- `GET /api/v1/portfolio/summary` — Portfolio-wide executive KPI metrics.
- `GET /api/v1/portfolio/exposure` — Exposure breakdown by risk and status.
- `GET /api/v1/portfolio/workload` — Reviewer workload allocations and overload warnings.
- `GET /api/v1/portfolio/cases/{case_id}` — Single portfolio case detail.
- `GET /api/v1/portfolio/cases/{case_id}/sla` — SLA deadline, elapsed time, and status.
- `GET /api/v1/portfolio/cases/{case_id}/priority` — Deterministic priority score and reasons.
- `POST /api/v1/portfolio/cases/{case_id}/assign` — Assign reviewer.
- `POST /api/v1/portfolio/cases/{case_id}/reassign` — Reassign reviewer.
- `POST /api/v1/portfolio/cases/{case_id}/unassign` — Remove active assignment.
- `GET /api/v1/portfolio/review-queue` — Cases requiring human review.
- `GET /api/v1/portfolio/overdue` — Cases violating SLA.
- `GET /api/v1/portfolio/high-risk` — Cases categorized as Critical or High risk.
