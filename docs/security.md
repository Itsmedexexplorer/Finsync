# VERITY Security & Hardening Architecture

**Day 12 Milestone: Production Hardening, Input Safety, and Defensive Controls**  
*Razorpay AI Buildathon 2026 | Track: AI Finance Controller*

---

## 1. Security Architecture Principles

VERITY enforces defense-in-depth across all pipeline layers. Security in VERITY is designed around the core tenet:

$$\textbf{VERITY must prefer uncertainty over an incorrect financial conclusion.}$$

```
+-------------------------------------------------------------------------------+
|                             CLIENT / API CALLER                               |
+-------------------------------------------------------------------------------+
                                      │
                                      ▼
+───────────────────────────────────────────────────────────────────────────────+
|                     SECURITY & LOGGING MIDDLEWARE LAYER                       |
|  • X-Request-ID Generation & Propagation                                      |
|  • Defensive Security Headers (nosniff, DENY, strict-origin, no-store)        |
|  • Configurable Strict CORS Origin Whitelist (No wildcard in production)      |
|  • Structured Request/Latency Auditing (Sanitized metadata only)              |
+───────────────────────────────────────────────────────────────────────────────+
                                      │
                                      ▼
+───────────────────────────────────────────────────────────────────────────────+
|                       INPUT VALIDATION & SANITIZATION                         |
|  • Strict Pydantic Schema Validation                                          |
|  • Filename Sanitization (Path traversal prevention, null-byte stripping)     |
|  • MIME Content-Type & Extension Whitelisting                                 |
|  • Max Upload File Size & Raw Text Length Bounds                              |
|  • Payload Cardinality Bounds (Max files, evidence items, txns, claims)       |
+───────────────────────────────────────────────────────────────────────────────+
                                      │
                                      ▼
+───────────────────────────────────────────────────────────────────────────────+
|                 ZERO-HALLUCINATION DETERMINISTIC REASONING                    |
|  • Immutable SHA-256 Content Fingerprints                                     |
|  • Strict Invariant Enforcement (No LLM in financial math / match decisions)  |
|  • Explicit Uncertainty Preservation (AMBIGUOUS, CONTRADICTED never confirmed)|
+───────────────────────────────────────────────────────────────────────────────+
                                      │
                                      ▼
+───────────────────────────────────────────────────────────────────────────────+
|                      STRUCTURED ERROR & AUDIT RESPONSES                       |
|  • Canonical ErrorResponse Contract (code, message, request_id)               |
|  • Full Internal Exception Logging (Tracebacks never leaked to client)        |
|  • Tamper-Evident SHA-256 Provenance DAG Lineage                              |
+───────────────────────────────────────────────────────────────────────────────+
```

---

## 2. Input Validation & File Upload Safety

### Filename Sanitization & Path Traversal Prevention
All uploaded file names and source identifiers pass through `SecurityValidator.sanitize_filename()`:
- Strips directory separators (`/`, `\`, `..`) preventing local directory traversal.
- Removes null bytes (`\0`) and illegal filesystem characters (`<>:"/\|?*`).
- Truncates filenames to 255 characters while preserving valid extensions.
- Empty or whitespace filenames safely default to `sanitized_evidence.txt`.

### MIME Type & Extension Whitelisting
Only supported multimodal financial formats are accepted:
- **Extensions**: `.csv`, `.pdf`, `.png`, `.jpg`, `.jpeg`, `.txt`
- **MIME Types**: `text/csv`, `application/pdf`, `image/png`, `image/jpeg`, `text/plain`
- Malformed or unsupported file uploads immediately return HTTP 415 with `UNSUPPORTED_MEDIA`.

### Resource Bounds & Request Size Limits
- **Max File Size**: Default `15.0 MB` (Configurable via `VERITY_MAX_UPLOAD_MB`). Returns HTTP 413 `FILE_TOO_LARGE`.
- **Max Text Evidence**: Default `250,000` characters (Configurable via `VERITY_MAX_TEXT_LENGTH`). Returns HTTP 400 `INVALID_INPUT`.
- **Max Files per Case**: Default `20` files.
- **Max Evidence Items**: Default `100` items.
- **Max Ledger Transactions**: Default `500` records.

---

## 3. Standardized Error Contract & Traceback Masking

All API errors return a uniform, machine-readable JSON structure:

```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "Field 'case_id': Field required",
    "request_id": "req-9b87f2e1a34d"
  }
}
```

### Stable Error Codes
| Error Code | HTTP Status | Description |
| :--- | :--- | :--- |
| `INVALID_INPUT` | 400 / 422 | Malformed JSON schema, field constraint violations, or text size limits. |
| `UNSUPPORTED_MEDIA` | 415 | Unsupported file extension or unapproved MIME type. |
| `FILE_TOO_LARGE` | 413 | Uploaded file exceeds configured byte limit. |
| `CASE_NOT_FOUND` | 404 | Case ID not present in session case store. |
| `RESOURCE_LIMIT` | 429 | Rate or cardinality bounds exceeded. |
| `PROCESSING_ERROR` | 400 / 500 | Pipeline processing constraint failure. |
| `INTERNAL_ERROR` | 500 | Unhandled server exception. Traceback is logged internally; client receives safe message with `request_id`. |

---

## 4. Defensive Security Headers & CORS

All HTTP responses automatically include defensive headers:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Cache-Control: no-store, no-cache, must-revalidate` (for dynamic `/api/*` endpoints)
- `X-Request-ID: req-...` (for end-to-end telemetry and support traceability)

CORS origins are strictly configured via `VERITY_CORS_ORIGINS`. Wildcard `*` origins are avoided in production configurations.
