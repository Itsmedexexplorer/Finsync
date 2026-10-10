# VERITY — Day 19: Proactive Controller Actions & Human-in-the-Loop Remediation

## Overview
Day 19 elevates VERITY from passive financial truth determination and cross-case intelligence to **proactive, fact-grounded controller actions and double-entry draft journal vouchers**, protected strictly by an **ironclad Human-in-the-Loop approval boundary**.

---

## 1. Strict Non-Negotiable Safety Invariants

1. **Zero Autonomous External Execution**: VERITY never sends emails, transmits messages, executes payments, or alters external ERP ledgers autonomously.
2. **Mandatory Human-in-the-Loop Approval**: Every remediation action begins in `PENDING_APPROVAL` status and transitions to `APPROVED` or `REJECTED` only via explicit controller action.
3. **Strict Fact Grounding (Zero Hallucination)**: Communication drafts cite only verified invoice numbers, bank UTRs, expected amounts, matched amounts, and discrepancy shortfalls derived directly from authoritative `ReconciliationResult` and `FinancialTruthReport`.
4. **Double-Entry Mathematical Balance**: All draft journal vouchers enforce `Total Debits == Total Credits` with mathematical rigor.
5. **Configurable Chart of Accounts (COA)**: Customer-specific COA mappings are supported. In the absence of a custom COA, vouchers use standardized placeholder accounts and explicitly flag `requires_account_mapping: true` with a `DRAFT JOURNAL VOUCHER` label.
6. **Immutable Audit Provenance**: Every proposed action, human approval, rejection, and journal export is cryptographically appended to the SHA-256 review audit hash chain.
7. **Financial Truth Immutability**: Proposing, approving, or rejecting remediation actions leaves historical reconciliation truth 100% unmutated.

---

## 2. Remediation Capabilities

### A. Fact-Grounded Communication Drafts
- **Vendor Dispute Notice (`VENDOR_DISPUTE_NOTICE`)**: Formal notice citing specific invoice numbers, UTRs, and shortfall amounts when contradictions or shortfalls are detected.
- **Payment Follow-Up Draft (`PAYMENT_FOLLOWUP_DRAFT`)**: Reminder notice requesting settlement of remaining unpaid balances for partially settled claims.
- **Missing Evidence Request (`MISSING_EVIDENCE_REQUEST`)**: Request to counterparty for bank statement proof, credit advice, or valid invoice documentation.

### B. Deterministic Draft Double-Entry Journal Vouchers (`DRAFT_JOURNAL_VOUCHER`)
- **Clean 1:1 Settlement (`CONFIRMED`)**:
  - `DR` Accounts Payable (Vendor Clearing)
  - `CR` Bank / Gateway Clearing Account
- **Partial Settlement (`PARTIAL` / `PARTIALLY_SETTLED`)**:
  - `DR` Accounts Payable (Matched Amount)
  - `DR` Unapplied Advance / Shortfall Clearing (Outstanding Amount)
  - `CR` Bank / Gateway Clearing Account (Total Claimed Obligation)
- **Contradicted Dispute Allocation (`CONTRADICTED`)**:
  - `DR` Reconciliation Suspense Account (Disputed Amount)
  - `CR` Accounts Payable / Disputed Liability (Disputed Amount)

---

## 3. Architecture & Components

```
                +---------------------------------------+
                |    Authoritative Financial Truth      |
                |  ReconciliationResult + TruthReport   |
                +-------------------+-------------------+
                                    |
          +-------------------------+-------------------------+
          |                                                   |
          v                                                   v
+-------------------------------+             +-------------------------------+
|   RemediationDraftGenerator   |             |      DraftJournalEngine       |
| (Dispute, Follow-up, Missing) |             |  (Double-Entry DR == CR Bal)  |
+---------------+---------------+             +---------------+---------------+
                |                                             |
                +---------------------+-----------------------+
                                      |
                                      v
                      +-------------------------------+
                      |     RemediationValidator      |
                      | (Grounding & Invariant Check) |
                      +---------------+---------------+
                                      |
                                      v
                      +-------------------------------+
                      |   RemediationActionService    |
                      | (PENDING_APPROVAL State Mach) |
                      +---------------+---------------+
                                      |
                    +-----------------+-----------------+
                    |                                   |
                    v                                   v
+-------------------------------+       +-------------------------------+
|       Human Reviewer          |       |        SQL Audit Store        |
|  (Approve / Reject Action)    | ----> |   (SHA-256 Hash Chain Event)  |
+-------------------------------+       +-------------------------------+
```

---

## 4. API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/cases/{case_id}/actions/propose` | Proposes a fact-grounded action (`VENDOR_DISPUTE_NOTICE`, `PAYMENT_FOLLOWUP_DRAFT`, `MISSING_EVIDENCE_REQUEST`, `DRAFT_JOURNAL_VOUCHER`). |
| `GET` | `/api/v1/cases/{case_id}/actions` | Lists all proposed and reviewed actions for a case. |
| `POST` | `/api/v1/cases/{case_id}/actions/{action_id}/approve` | Explicit human approval of a proposed action. Emits `ACTION_APPROVED` into audit hash chain. |
| `POST` | `/api/v1/cases/{case_id}/actions/{action_id}/reject` | Explicit human rejection with controller reason. Emits `ACTION_REJECTED` into audit hash chain. |
| `GET` | `/api/v1/cases/{case_id}/journal-voucher` | Retrieves the balanced draft double-entry journal voucher. |
| `POST` | `/api/v1/cases/{case_id}/journal-voucher/export` | Exports draft journal voucher (JSON) and records `JOURNAL_EXPORTED` in audit store. |

---

## 5. Verification Metrics

- **Day 19 Evaluator (`scripts/evaluate_remediation.py`)**: **12 / 12 (100.0%) PASS**
- **Unit Test Suite (`tests/unit/remediation/`)**: **16 / 16 (100.0%) PASS**
- **Overall Pytest Suite**: **354 / 354 PASS (100%)**
- **Benchmark Cases (`data/benchmark/ground_truth_cases.json`)**: **96 / 96 Untouched**
- **Double-Entry Imbalances**: **0 (TARGET: 0)**
- **Ungrounded / Fabricated Claims**: **0 (TARGET: 0)**
- **Autonomous External Dispatches**: **0 (TARGET: 0)**
