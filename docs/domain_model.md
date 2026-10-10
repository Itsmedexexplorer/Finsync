# VERITY Canonical Domain Model Specification

**Core Principle: Evidence ≠ Claim ≠ Conclusion**

---

## 1. The Core Principle in Action

Financial data in real-world Indian SMBs is noisy, unverified, and fragmented. Existing systems frequently make the fatal mistake of conflating what an artifact says with what actually happened.

### Concrete Example:
```
1. EVIDENCE:
   - Modality: MESSAGING_CHAT (WhatsApp)
   - Raw Text: "Bhai maine 20,000 GPay kar diya check karo"
   - Captured: 2026-08-14 10:15:00 UTC

2. CLAIM:
   - Type: PAYMENT_SENT
   - Claimed Amount: ₹20,000.00
   - Counterparty Hint: "Ramesh"
   - Payment Rail Hint: "UPI / GPAY"
   - Status: ASSERTED (Not yet verified!)

3. SEPARATE EVIDENCE & TRANSACTION:
   - Modality: BANK_STATEMENT (HDFC Bank CSV)
   - Narration: "UPI/408219381920/RAMESH/PAYMENT"
   - Verified Amount: ₹18,500.00 CREDIT

4. CONCLUSION (RECONCILIATION RESULT):
   - Status: PARTIAL
   - Reconciled Amount: ₹18,500.00
   - Outstanding Amount: ₹1,500.00
   - Discrepancy: AMOUNT_MISMATCH (Expected 20,000.00, Observed 18,500.00)
   - Confidence: 0.92
```

By decoupling Evidence, Claim, and Conclusion, VERITY never blindly trusts text or screenshots, nor does it drop unverified evidence.

---

## 2. Model Schemas & Specifications

### 2.1 `Evidence`
Represents an uninterpreted artifact captured from the real world.
- `id` (str): Unique evidence identifier (e.g. `EVID-2026-001`).
- `modality` (`BANK_STATEMENT`, `INVOICE`, `RECEIPT`, `PAYMENT_SCREENSHOT`, `MESSAGING_CHAT`, `CASH_VOUCHER`, `PAYMENT_GATEWAY_EXPORT`).
- `source_type` (`BANK_CSV`, `BANK_PDF`, `WHATSAPP_EXPORT`, `ZOHO_INVOICE`, `RAZORPAY_FEED`, `PAPER_SCAN`).
- `source_name` (str): Filename or stream origin.
- `raw_payload` (str): Complete unparsed string/payload.
- `content_hash` (str): SHA-256 hash computed upon initialization.
- `language_hint` (str): e.g. `en`, `hi`, `hi-Latn`, `ta-Latn`.
- `received_at` (datetime): UTC timestamp.

### 2.2 `Claim`
Represents an assertion extracted from an Evidence item.
- `id` (str): Unique claim identifier (e.g. `CLM-2026-001`).
- `evidence_id` (str): Foreign key to the parent `Evidence`.
- `claim_type` (`PAYMENT_SENT`, `PAYMENT_RECEIVED`, `INVOICE_ISSUED`, `CASH_PAYMENT_PROMISE`, `REFUND_REQUESTED`, `DISCOUNT_APPLIED`).
- `claimed_amount` (float): Numeric asserted value (must be >= 0).
- `claimed_date` (Optional[str]): Asserted date.
- `counterparty_hint` (Optional[str]): Party name/handle.
- `reference_id_hint` (Optional[str]): Asserted UTR/RRN/Cheque reference.
- `confidence` (float): Extraction confidence (0.0 to 1.0).
- `raw_text_snippet` (Optional[str]): Verbatim snippet from evidence.
- `status` (`ASSERTED`, `VALIDATED`, `REFUTED`, `AMBIGUOUS`, `SUPERSEDED`).

### 2.3 `Entity`
Represents a resolved business entity or counterparty.
- `id` (str): Unique entity ID.
- `canonical_name` (str): Standard legal or primary trading name.
- `entity_type` (`INDIVIDUAL`, `FREELANCER`, `SOLE_PROPRIETORSHIP`, `PRIVATE_LIMITED`, `PARTNERSHIP`, `LLP`).
- `gstin` (Optional[str]): 15-digit GST identification number.
- `pan` (Optional[str]): 10-digit PAN.
- `upi_ids` (List[str]): Virtual Payment Addresses.
- `bank_accounts` (List[BankAccountIdentifier]): Linked bank accounts.
- `phone_numbers` (List[str]): Normalized phone numbers.
- `aliases` (List[str]): Discovered trading aliases and nick names.

### 2.4 `Transaction`
Represents a verified ledger movement (backed by bank / gateway).
- `id` (str): Unique transaction ID.
- `amount` (float): Verified monetary value (> 0).
- `direction` (`CREDIT`, `DEBIT`).
- `payment_method` (`UPI`, `NEFT`, `RTGS`, `IMPS`, `CARD`, `NETBANKING`, `CASH`, `GATEWAY`, `CHEQUE`).
- `bank_reference` (Optional[str]): Official bank UTR, UPI RRN, or IMPS reference.
- `narration` (Optional[str]): Raw statement narration line.
- `evidence_ids` (List[str]): Supporting evidence IDs.

### 2.5 `Discrepancy`
Represents an anomaly or exception identified during reconciliation.
- `id` (str): Discrepancy identifier.
- `discrepancy_type` (`AMOUNT_MISMATCH`, `DATE_OUT_OF_WINDOW`, `CONTRADICTORY_CLAIM`, `MISSING_EVIDENCE`, `DUPLICATE_EVIDENCE`, `UNRESOLVED_ENTITY`, `INVALID_REFERENCE_ID`, `UNVERIFIABLE_CASH_CLAIM`, `PARTIAL_SETTLEMENT`, `AMBIGUOUS_MATCH`).
- `severity` (`INFO`, `WARNING`, `ERROR`, `CRITICAL`).
- `message` (str): Clear human explanation.
- `expected_value` / `observed_value` (Optional[str]): Quantitative comparison.

### 2.6 `ReconciliationRecord`
The synthesized conclusion.
- `id` (str): Unique reconciliation result ID.
- `status` (`CONFIRMED`, `PARTIAL`, `DUPLICATE`, `CONTRADICTED`, `UNVERIFIABLE`, `AMBIGUOUS`).
- `match_type` (`EXACT_1_TO_1`, `ONE_TO_MANY`, `MANY_TO_ONE`, `PARTIAL_PAYMENT`, `CROSS_MODAL_DUPLICATE`, `CONTRADICTED_ASSERTION`, `UNMATCHED`).
- `expected_amount` (Optional[float]): Total expected amount.
- `reconciled_amount` (float): Total verified ledger amount.
- `outstanding_amount` (float): Remaining unpaid balance.
- `confidence_score` (float): 0.0 to 1.0.
- `explanation_summary` (str): Complete human-readable justification.
- `discrepancies` (List[Discrepancy]): Attached anomalies.
