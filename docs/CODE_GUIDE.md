# FinSync code guide

This guide explains how FinSync is built: what each feature does, where its code lives, and how
the parts fit together. Every file in `backend/` and `frontend/` also starts with a comment that
explains it, and every function has a one-line description.

FinSync makes every decision with **fixed rules**. It does not use any AI model. Pictures are
read with the Tesseract OCR program, and the same rules are then applied to the text.

---

## 1. The big picture

```
Browser (frontend/app.js)
   │  uploads files, shows results          HTTPS + Supabase sign-in token
   ▼
FastAPI server (backend/api)
   │  checks sign-in and limits, opens the user's private workspace
   ▼
8-stage pipeline (backend/case_processing/pipeline.py)
   1 Ingest  →  2 Extract (rules + OCR)  →  3 Resolve names  →  4 Match
   →  5 Remove duplicates  →  6 Find contradictions  →  7 Reconcile  →  8 Report
   │
   ▼
User's SQLite workspace (backend/workspace.py, backend/storage)  ──backup──▶  Supabase Storage
```

## 2. What happens when you click "Check payments"

1. **Browser** – `runCheck()` in `frontend/app.js` sends every file to `POST /api/v1/batches/files`.
2. **Sign-in and limits** – `backend/api/auth.py` checks the Supabase token, applies rate limits
   (`backend/api/rate_limit.py`) and opens that user's workspace (`backend/workspace.py`).
3. **Upload checks** – `backend/api/routes.py` (`submit_batch_files`) checks each file's type and
   size (`backend/api/security.py`) and saves it to a temporary folder.
4. **Split into payments** – `backend/case_processing/batch.py` reads every file once and groups
   the claims into payments (same UTR / UPI reference, otherwise same person and amount).
   One payment → a normal check. Several → one check per payment plus a summary.
5. **Pipeline** – each payment goes through the 8 stages below.
6. **Save** – the result is stored in the user's SQLite database and backed up.
7. **Show** – the browser opens the check page (`viewCheck`) or the upload summary (`viewBatch`).

## 3. The 8 stages and their files

| Stage | What it does | Main files |
|---|---|---|
| 1. Ingest | Recognises each file (bank statement, invoice, screenshot, chat) and turns it into evidence items. A bank statement becomes one item per row. | `backend/ingestion/csv_adapter.py`, `pdf_adapter.py`, `pdf_statement.py`, `image_adapter.py`, `text_adapter.py` |
| 2. Extract | Finds amount, UTR / UPI reference, date, person, payment method and direction with fixed rules. Images and scanned PDFs are read with OCR first. | `backend/extraction/text_extractor.py`, `ocr_extractor.py`, `pdf_extractor.py`, `bank_csv_extractor.py`, `document_fields.py` |
| 2b. Corrections | Fixes a one-character OCR slip in a UTR; recognises bills the user paid (money out). | `backend/case_processing/ocr_reference.py`, `bill_direction.py` |
| 3. Resolve names | Links the same person written differently, using GSTIN, PAN, UPI id, phone and name. | `backend/entity_resolution/` |
| 4. Match | Scores every claim against every bank line with fixed weights; finds part payments and split payments. | `backend/transaction_matching/signals.py`, `engine.py`, `combiner.py` |
| 5. Duplicates | Groups the same file or the same payment reported twice, so it is counted once. | `backend/deduplication/` |
| 6. Contradictions | Flags differences in amount, date, reference, person or direction. | `backend/contradiction_detection/` |
| 7. Reconcile | Decides the final status and the amount received and still due. | `backend/reconciliation/engine.py`, `rules.py` |
| 8. Report | Writes the plain-English summary, reasons and next steps. | `backend/reporting/` |

## 4. Matching rules (stage 4)

Each signal has a fixed weight (`backend/transaction_matching/signals.py`):

| Signal | Weight |
|---|---|
| Same UTR / UPI reference | 1.00 |
| Invoice number in the bank narration | 1.00 |
| Same payer (GSTIN, PAN, UPI id, phone) | 0.90 |
| Exact amount | 0.80 |
| Date within 7 days | 0.70 |
| Same payment method | 0.60 |
| Person's name in the narration | 0.55 |
| Smaller amount (part payment) | 0.50 |

Score = strongest signal + 0.04 for each extra signal (max 1.0), minus 0.35 for each conflict.
0.85 or more is matched; 0.60–0.84 is probable; two candidates within 0.15 of each other with no
reference to decide between them make the check **Unclear**, and the user chooses.

## 5. Results the user sees

| Shown as | Internal status | Meaning |
|---|---|---|
| Matched | CONFIRMED | The full amount is in the bank. |
| Part paid | PARTIALLY_SETTLED | Only part arrived; the rest is still due. |
| Mismatch | CONTRADICTED | The evidence disagrees (amount, date, reference, person or direction). |
| Unclear | AMBIGUOUS | More than one bank line could fit; the user picks. |
| No bank proof | UNVERIFIABLE | Nothing in the bank supports the claim. |

## 6. Reading pictures (OCR)

`backend/extraction/ocr_extractor.py`:

1. **Prepare the image** – grayscale, invert dark-mode screenshots, stretch the contrast.
2. **Read** – Tesseract reads the page as one column; if no amount is found it reads again as
   scattered text.
3. **Repair amounts** – Tesseract has no ₹ sign and makes typical mistakes, which are repaired
   with fixed rules: ₹ read as a symbol or digit (the first character's shape is checked), 7 read
   as "/", a comma read as a space, a space next to a comma.
4. **Extract** – the text goes to the same rules as typed text. Claims read by OCR get slightly
   lower confidence (×0.9).

## 7. Frontend

`frontend/app.js` (plain JavaScript, no framework):

- `render()` is the router: the address after `#` decides which `view...()` function draws the page.
- `api()` calls the backend with the sign-in token.
- Home dashboard: `viewHome`, `reconTable`, `statusDonut`, `collectionBar`.
- New check: `viewNew`, `runCheck`.
- One check: `viewCheck` and its tabs (`renderSummaryTab`, `renderRecordsTab`, `renderReviewTab`,
  `renderFollowupsTab`, `renderHistoryTab`).
- One upload with many payments: `viewBatch`.
- Sign-in (email/password and Google): `initAuth`, `renderAuth`.

`frontend/styles.css` defines colours and spacing once as CSS variables; the dark theme only
redefines those variables.

## 8. Security and privacy

| Feature | Where |
|---|---|
| Sign-in with Supabase (email or Google); every API call needs a valid token | `backend/api/auth.py`, `frontend/app.js` (`initAuth`) |
| A private SQLite database per user | `backend/workspace.py` |
| File type and size checks; text length limit | `backend/api/security.py` |
| Rate limits per IP and per user | `backend/api/rate_limit.py` |
| Tamper-evident history (each event holds the SHA-256 of the previous one) | `backend/storage/audit_store.py`, `backend/review/` |
| Security headers on every response | `backend/api/app.py` |
| Everything shown in the browser is escaped (no XSS) | `esc()` in `frontend/app.js` |
| Uploaded files are deleted after processing | `backend/api/routes.py` (`finally: shutil.rmtree`) |

## 9. Tests

`tests/` holds 475+ automated tests (`python -m pytest`). Important ones for the main features:

- `tests/unit/case_processing/test_statements_and_bills.py` – CSV and PDF statements, bills paid,
  OCR fixes, matching edge cases.
- `tests/unit/case_processing/test_batch_upload.py` – many payments in one upload.
- `tests/unit/extraction/test_ocr_extractor.py` – reading pictures.

## 10. Other folders

| Folder | What it is |
|---|---|
| `backend/review/` | The user's answers on a check and their history. |
| `backend/controller/` | Priority, next actions and answers to "Ask about this check", all from fixed rules and templates. `ai_explainer.py` also holds an optional AI part that is switched off and never called. |
| `backend/controller/remediation/` | Ready-to-send follow-up drafts for money still due. |
| `backend/cross_case/` | Looks across the user's earlier checks (repeat references, repeat problems). |
| `backend/portfolio/` | All checks with priorities, for the lists and badges. |
| `backend/provenance/` | Records which file each claim and result came from. |
| `backend/extraction/ai_provider.py` | An optional AI reader kept as a plug-in point. **Not used**: switched off (MOCK). |
| `supabase/` | Email templates and sign-in settings. |
| `data/samples`, `data/benchmark` | Sample data used by tests and demos. |
