# VERITY Human Review, Case Investigation & Audit Workflow

**Day 14 Milestone: Human Review, Case Investigation & Tamper-Evident Audit Subsystem**  
*Razorpay AI Buildathon 2026 | Track: AI Finance Controller*

---

## 1. Core Architectural Separation

The **VERITY Human Review Subsystem** serves as an audit-compliant, decision-recording workspace for human finance controllers.

$$\textbf{CORE INVARIANT: HUMAN REVIEW DECISION } \neq \textbf{ DETERMINISTIC FINANCIAL TRUTH.}$$

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
                │  • Deterministic Workflow State Machine                     │
                │  • Append-Only Review Notes & Evidence Inspection Tracking  │
                │  • Granular Investigation Tasks (Checklist)                 │
                │  • Non-Destructive Decision Recording                       │
                │  • Tamper-Evident SHA-256 Chained Audit Trail               │
                └─────────────────────────────────────────────────────────────┘
```

### Critical Boundaries:
1. **No Fact Mutation**: A human reviewer choosing `CONFIRMED` on a case whose deterministic status is `CONTRADICTED` does **NOT** alter the deterministic status to `CONFIRMED`. The system records:
   - `deterministic_status`: `CONTRADICTED`
   - `human_review_decision`: `CONFIRMED`
   - `review_status`: `RESOLVED`
2. **Evidence Immutability**: Marking an evidence artifact as reviewed records an `EvidenceReviewRecord` in the review store; the underlying `Evidence` object and its cryptographic SHA-256 hash remain completely untouched.
3. **Cross-Case Protection**: References to evidence, claim, or transaction IDs not belonging to the case are rejected with `InvalidReferenceError`.

---

## 2. Review Workflow State Machine

The review lifecycle is strictly governed by `ReviewWorkflow`:

$$\text{NOT\_REQUIRED} \longrightarrow \text{PENDING} \longrightarrow \text{IN\_PROGRESS} \longrightarrow \text{RESOLVED} \longrightarrow \text{CLOSED}$$
$$\text{IN\_PROGRESS} \longleftrightarrow \text{ESCALATED}$$

### Transition Rules:
- Direct jump from `PENDING` to `CLOSED` is **REJECTED** (`InvalidStateTransitionError`).
- Reopening a `CLOSED` review is **REJECTED**.
- In terminal `CLOSED` state, all mutations (adding notes, inspecting evidence, completing actions) are permanently locked (`ReviewClosedError`).

---

## 3. Tamper-Evident Cryptographic Audit Chaining

Every review mutation produces an `AuditEvent` cryptographically linked to the previous event:

$$\text{Hash}_0 = \text{SHA-256}(\text{GENESIS} \parallel \text{Event}_0)$$
$$\text{Hash}_i = \text{SHA-256}(\text{Hash}_{i-1} \parallel \text{Event}_i)$$

If any audit event description, actor, timestamp, or affected ID is altered in-place, `AuditTrail.verify_chain()` immediately detects an integrity failure.

---

## 4. API Endpoints Reference

- `GET /api/v1/cases/{case_id}/review` — Retrieves or initializes review record.
- `POST /api/v1/cases/{case_id}/review/start` — Transitions review to `IN_PROGRESS`.
- `POST /api/v1/cases/{case_id}/review/note` — Appends timestamped note.
- `POST /api/v1/cases/{case_id}/review/evidence/{evidence_id}` — Marks evidence inspected.
- `POST /api/v1/cases/{case_id}/review/action` — Creates investigation task.
- `POST /api/v1/cases/{case_id}/review/action/{action_id}/complete` — Completes task.
- `POST /api/v1/cases/{case_id}/review/decision` — Records human review verdict.
- `POST /api/v1/cases/{case_id}/review/escalate` — Escalates review.
- `POST /api/v1/cases/{case_id}/review/resolve` — Marks review `RESOLVED`.
- `POST /api/v1/cases/{case_id}/review/close` — Seals review `CLOSED`.
- `GET /api/v1/cases/{case_id}/review/audit` — Retrieves audit event history.
- `GET /api/v1/cases/{case_id}/review/audit/verify` — Validates cryptographic chain integrity.
- `GET /api/v1/cases/{case_id}/review/summary` — Returns synthesized executive review summary.
