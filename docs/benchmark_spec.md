# VERITY Ground-Truth Benchmark Specification

**Total Cases**: 96 Realistic Scenarios  
**Coverage**: 12 Distinct Indian Financial Categories  
**Determinism**: 100% Independently Defined Ground Truth (Zero LLM Dependency)

---

## 1. Category Distribution & Taxonomy

| Category | Cases | Description | Dominant Modalities | Expected Statuses |
|---|---|---|---|---|
| `CLEAN_1TO1` | 10 | Clean 1:1 invoice to transaction match with exact UTR and amounts. | `INVOICE`, `BANK_STATEMENT` | `CONFIRMED` |
| `ONE_TO_MANY` | 8 | 1 consolidated bank payment settling N invoices (bulk settlement). | `INVOICE` (N), `BANK_STATEMENT` (1) | `CONFIRMED` |
| `MANY_TO_ONE` | 8 | N milestone installments settling 1 large invoice (e.g. 50-50, 40-30-30). | `INVOICE` (1), `BANK_STATEMENT` (N) | `CONFIRMED` |
| `PARTIAL_PAYMENTS` | 8 | Payment covers part of invoice; computes open balance with chat acknowledgment. | `INVOICE`, `BANK_STATEMENT`, `MESSAGING_CHAT` | `PARTIAL` |
| `CROSS_MODAL_DUPLICATES` | 8 | WhatsApp screenshot + Bank statement line for the same UTR and amount. | `PAYMENT_SCREENSHOT`, `BANK_STATEMENT` | `DUPLICATE` |
| `CONTRADICTORY_CLAIMS` | 8 | Chat claims paid / full amount, but bank shows lesser credit, zero credit, or bounce. | `MESSAGING_CHAT`, `BANK_STATEMENT` | `CONTRADICTED` |
| `MISSING_EVIDENCE` | 8 | Unmatched bank inflows without invoices, or unpaid invoices with zero settlement. | `BANK_STATEMENT` or `INVOICE` | `UNVERIFIABLE` |
| `IDENTITY_NAME_VARIATIONS` | 8 | Legal entity name vs proprietor name vs WhatsApp nick vs UPI VPA handles. | `INVOICE`, `BANK_STATEMENT` | `CONFIRMED` |
| `INCORRECT_REF_IDS` | 8 | Transposition error / 1-character typo in UTR in chat vs bank record. | `MESSAGING_CHAT`, `BANK_STATEMENT` | `CONFIRMED` (with `INVALID_REFERENCE_ID`) |
| `CASH_PAYMENT_CLAIMS` | 6 | Cash handover assertions in WhatsApp or handwritten paper chits without bank trail. | `MESSAGING_CHAT`, `CASH_VOUCHER`, `INVOICE` | `UNVERIFIABLE` |
| `MULTILINGUAL_HINGLISH` | 8 | Payment confirmations in Hindi, Hinglish, Tamil, Kannada, Telugu, Bengali. | `MESSAGING_CHAT`, `INVOICE`, `BANK_STATEMENT` | `CONFIRMED` |
| `AMBIGUOUS_CASES` | 8 | Multiple open identical invoices to same vendor with single unreferenced credit. | `INVOICE` (N), `BANK_STATEMENT` (1) | `AMBIGUOUS` |

---

## 2. Benchmark Case Structure

Each case in `data/benchmark/ground_truth_cases.json` conforms to the following schema:
- `case_id` (str): Unique slug.
- `category` (str): One of the 12 categories.
- `scenario_title` (str): Descriptive title.
- `description` (str): Contextual scenario summary.
- `language` (str): Primary language of chat/evidence (`en`, `hi`, `hi-Latn`, `ta-Latn`, `kn-Latn`, `te-Latn`, `bn-Latn`).
- `entity` (Optional[Entity]): Canonical counterparty with aliases and identifiers.
- `evidence` (List[Evidence]): Array of raw evidence items with SHA-256 hashes.
- `claims` (List[Claim]): Structured assertions extracted from evidence.
- `transactions` (List[Transaction]): Verified ledger entries.
- `ground_truth` (GroundTruthExpectation):
  - `expected_status`: `CONFIRMED`, `PARTIAL`, `DUPLICATE`, `CONTRADICTED`, `UNVERIFIABLE`, `AMBIGUOUS`.
  - `expected_match_type`: Topological match type.
  - `expected_reconciled_amount`: Verified ledger amount.
  - `expected_outstanding_amount`: Unsettled balance.
  - `expected_discrepancies`: List of expected discrepancy types.
  - `confidence_threshold`: Minimum confidence score expected.
  - `resolution_notes`: Clear deterministic justification.
