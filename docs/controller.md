# VERITY AI Finance Controller & Decision Intelligence

**Day 13 Milestone: Explainable AI Controller, Decision Intelligence & Grounded Explainability**  
*Razorpay AI Buildathon 2026 | Track: AI Finance Controller*

---

## 1. Architectural Philosophy & Safety Boundaries

The **VERITY AI Finance Controller** operates strictly as an intelligent decision-support and explainability layer above the deterministic reconciliation engine.

$$\textbf{Core Principle: AI MAY EXPLAIN DETERMINISTIC RESULTS. AI MUST NEVER OVERRIDE DETERMINISTIC FINANCIAL TRUTH.}$$

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
                │  • Deterministic Signal Extraction                          │
                │  • Policy Risk Classification (CRITICAL / HIGH / MED / LOW) │
                │  • Deterministic Action Prioritization                      │
                │  • Evidence-Grounded Explainability & Rationale             │
                └──────────────────────────────┬──────────────────────────────┘
                                               │
                                               ▼
                ┌─────────────────────────────────────────────────────────────┐
                │           OPTIONAL AI EXPLAINER & FACT-CHECKER              │
                │                                                             │
                │  • Strict Fact Checking (No fabricated amounts/entities)    │
                │  • Deterministic Template Fallback on Validation Failure    │
                │  • Natural-Language Grounded Q&A                            │
                └─────────────────────────────────────────────────────────────┘
```

### Authoritative Deterministic Boundaries
1. **Mathematical Invariants**: Amounts, balances, transactions, and match relationships are solely determined by Days 1–8 deterministic logic.
2. **Zero Fabrication**: The AI layer never invents amounts, counterparties, UTRs, dates, or missing evidence.
3. **Strict Validation**: All natural language output is checked against source facts. If an ungrounded figure or status contradiction is found, output is rejected immediately in favor of deterministic templates.

---

## 2. Controller Models & Decision Intelligence

### Risk Severity (`ControllerRiskLevel`)
- `CRITICAL`: Severe contradiction (e.g. `ENTITY_MISMATCH`, `DIRECTION_MISMATCH`, or critical amounts). Automated ledger posting is blocked.
- `HIGH`: Unresolved ambiguity, material amount discrepancy, or reference mismatch.
- `MEDIUM`: Partial settlements with outstanding balances, unlinked bank transactions, or unverifiable claims.
- `LOW` / `NONE`: Confirmed clean cases with zero discrepancies.

### Action Directives (`ControllerActionType`)
- `INVESTIGATE_CONTRADICTION`: Audit discrepancies between invoices and bank records.
- `VERIFY_ENTITY`: Confirm counterparty identities and PAN/GSTIN associations.
- `VERIFY_TRANSACTION`: Track remaining balance or identify unmatched credit sources.
- `REVIEW_CASE`: Disambiguate multiple candidate transaction matches.
- `REQUEST_MISSING_EVIDENCE`: Solicit formal bank receipts or proof of payment for informal claims.
- `CONFIRM_RECONCILIATION`: Authorize automated ledger posting.
- `NO_ACTION`: Case fully settled.

---

## 3. Prioritization & Grounded Explainability

Recommendations are deterministically ordered by urgency:
1. **Rank 1**: Critical Entity & Direction Mismatches
2. **Rank 2**: Amount & Bank Reference Contradictions
3. **Rank 3**: Multiple Ambiguous Candidates
4. **Rank 4**: Partial Settlements & Outstanding Balance Follow-ups
5. **Rank 5**: Unmatched Bank Ledger Credits
6. **Rank 6**: Informal Unverified Claims
7. **Rank 7**: Clean Settlement Approvals

---

## 4. API Endpoints

- `GET /api/v1/cases/{case_id}/controller` — Returns `ControllerDecision` with risk level, action, review flag, and reasons.
- `GET /api/v1/cases/{case_id}/controller/brief` — Returns executive `ControllerBrief` synthesizing risks, financial metrics, and recommendations.
- `POST /api/v1/cases/{case_id}/controller/explain` — Answers natural language queries grounded in deterministic facts.
