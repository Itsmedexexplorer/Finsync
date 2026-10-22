<p align="center">
  <img src="frontend/assets/logo.svg" width="72" alt="FinSync logo">
</p>

<h1 align="center">FinSync</h1>
<p align="center"><b>Know who has really paid you.</b><br>
FinSync checks invoices, payment messages and screenshots against your bank statement and tells you, in plain words, what actually reached your account.</p>

<p align="center"><a href="https://finsync-vv9c.onrender.com">Live app</a> · Rule-based · No AI · 417 automated tests</p>

---

## What is FinSync?

Small businesses, agencies and freelancers in India get payment proof from all over the place:

- "Bhai 35,000 GPay kar diya, check kar lo" on WhatsApp
- A PhonePe or Paytm screenshot
- A PDF invoice from Zoho or Tally
- The bank statement, which is the only record that shows money actually arrived

A message or screenshot only shows that someone *says* they paid. FinSync treats your **bank statement as the source of truth** and checks every claim against it.

FinSync is **not AI-powered**. Reading files, matching payments, working out amounts and choosing a status are all done by fixed rules, so the same files always give the same result and every number can be traced back to a record.

## What you get for each check

| Status | What it means |
|---|---|
| **Matched** | The payment is in your bank statement, for the right amount. |
| **Part paid** | Some money arrived, but less than what was billed or promised. |
| **Mismatch** | Your records disagree with the bank (amount, reference number, person, date or direction of money). |
| **No bank proof** | Someone says they paid, but there's no matching bank entry. |
| **Unclear** | More than one bank entry could match, so you need to pick. |
| **Duplicate** | The same payment appears twice (e.g. a message and a bank line). It's only counted once. |
| **Unmatched** | A bank entry or bill with nothing to pair it with yet. |

Each check also shows:

- **expected vs. received vs. still due**
- a list of **what didn't add up**, with how serious each issue is
- **next steps**
- an **Ask** box for quick questions about the check, such as *why does this need review?*, *how much is still due?* or *what proof is there?* Answers are built from the check's own facts using fixed templates, so they can't invent numbers.

## How to use it

1. **Sign up.** Every account gets its own private workspace, and it starts empty.
2. **Take the tour.** A short walkthrough opens on your first visit and points out each part of the app. You can replay it anytime from *How it works* or *Account*.
3. **Start a check.** Tap **New check** and add:
   - your **bank statement** as a CSV (net-banking export or a Razorpay settlement report). This is the most important file.
   - any **invoices** (PDF), **chat exports** (TXT) or **payment screenshots** (PNG/JPG/JPEG). You can also paste a message.
   - up to 20 files per check, 15 MB each.
4. **Read the verdict.** FinSync reads the files, matches every claim to a bank entry and shows the result.
5. **Answer one question.** If something doesn't add up, FinSync asks you a plain question (e.g. "Did Vikram pay you only ₹12,000?") and shows what was claimed next to what your bank shows, with the difference highlighted. Pick the answer that fits and add a note if you like. Your answer is saved with the check; it never changes the bank figures.
6. **Follow up.** Create a payment reminder, a dispute notice, a request for proof, or a draft accounting entry. FinSync fills in the draft from the facts in the check; you copy it and send it yourself.
7. **Track people.** The *People* page totals what each customer or vendor has paid and still owes across all your checks.

### What FinSync can read

| File | How it's read |
|---|---|
| Bank statement (CSV) | Each row becomes a bank transaction (date, amount, direction, UTR/reference, narration). |
| Invoice (PDF with selectable text) | Invoice number, amount and date are picked out of the text. |
| Chat export (TXT) or pasted message | Payment claims like "35,000 GPay kar diya" are picked out of the text: English, Hinglish and common phrases in Hindi, Marathi, Tamil, Telugu, Kannada and Bengali. |
| Screenshot (PNG/JPG) or scanned PDF | **Text inside images isn't read.** The file is kept as evidence that someone says they paid, but without an amount. To have the amount checked, paste the payment message or add a text PDF. |

### Pages

| Page | What it's for |
|---|---|
| **Home** | Totals: checks run, money confirmed in bank, still due, checks needing review |
| **New check** | Upload files or paste a message, then run the check |
| **Checks** | Every check with its verdict. Filter by *Needs review*, *Matched*, *Money due*, *Mismatch* |
| **Check details** | Verdict, amounts, issues, next steps, Ask, plus tabs for Records, Your answer, Follow-ups and History |
| **People** | Customers and vendors with paid/due totals |
| **How it works** | Status meanings, file types, FAQ, replay the tour |
| **Account** | Profile, change password, sign out |

The app is responsive: it has a bottom tab bar on phones and a sidebar on larger screens. It has a light and a dark theme; by default it follows your device setting, and you can switch it from the sidebar or *Account*.

## How it works under the hood

```
Browser (frontend/)                     Server (backend/, Python + FastAPI)
┌───────────────────────┐   HTTPS +     ┌──────────────────────────────────────────────┐
│ Plain HTML/CSS/JS app │  Supabase JWT │ Auth middleware → verifies the token with    │
│ (no framework, no     │ ────────────▶ │   Supabase, opens that user's workspace      │
│  build step)          │               │                                              │
│ • Supabase sign-in    │               │ Rule-based pipeline (per check)              │
│ • Hash router         │               │  1 Ingest files (CSV, PDF, image, text)      │
│ • Guided tour         │               │  2 Extract claims; bank rows → transactions  │
└───────────────────────┘               │  3 Resolve who's who (names, UPI, GSTIN, PAN)│
                                        │  4 Match claims ↔ bank (1:1, 1:N, N:1)       │
                                        │  5 Remove duplicates across files            │
                                        │  6 Detect contradictions                     │
                                        │  7 Reconcile → status + amounts              │
                                        │  8 Plain-language report + audit trail       │
                                        │                                              │
                                        │ Workspace per user: SQLite DB + review state │
                                        └───────────────┬──────────────────────────────┘
                                                        │ snapshot after every change
                                                        ▼
                                          Supabase Storage (private "workspaces" bucket)
```

- **Rules, not AI.** Every stage above is deterministic code: parsers, matching rules and fixed thresholds. There are no model calls and no API keys for AI services.
- **What matching looks at:** amount, date, UTR/reference number, invoice number, who paid (name, UPI ID, GSTIN, PAN) and the direction of money. It can pair one claim with one bank entry, one invoice with several bank entries that add up to it, or one bank entry with several invoices it covers.
- **Each user's data is kept separate.** Every user has their own workspace (`data/workspaces/<user-id>/`) with its own SQLite database. Users can't see each other's checks or people.
- **Data survives restarts.** Free hosting wipes the server's disk on every restart. After each change, FinSync uploads a snapshot of your workspace to a private Supabase Storage bucket and restores it automatically the next time you sign in.
- **Uploaded files aren't kept.** They're written to a temp folder, processed and deleted. Only the results are stored.
- **History can't be changed quietly.** Review activity is hash-chained (SHA-256), and *History → Verify* checks that nothing was edited.

### Tech stack

| Part | What's used |
|---|---|
| Frontend | Plain HTML, CSS and JavaScript (`frontend/`) |
| Backend | Python 3.10+, FastAPI, Pydantic, pypdf |
| Storage | SQLite (one database per user), backed up to Supabase Storage |
| Sign-in | Supabase Auth |
| Hosting | Render (free tier), or any Docker host |
| Tests | pytest (417 tests) |

### Main code locations

| Path | What's there |
|---|---|
| `frontend/` | The whole web app: `index.html`, `styles.css`, `app.js`, logo/icons |
| `backend/api/` | FastAPI app, routes, auth middleware (`auth.py`), web-app endpoints (`user_routes.py`), rate limits |
| `backend/workspace.py` | Per-user workspaces |
| `backend/cloud_sync.py` | Backup/restore to Supabase Storage |
| `backend/case_processing/` | Runs the 8-stage pipeline |
| `backend/ingestion`, `extraction`, `entity_resolution`, `transaction_matching`, `deduplication`, `contradiction_detection`, `reconciliation`, `reporting` | One folder per pipeline stage |
| `backend/review`, `backend/controller` | Review workflow, Ask answers, next-step suggestions, follow-up drafts and journal entries |
| `backend/storage`, `portfolio`, `cross_case`, `provenance`, `domain` | Database layer, totals across checks, people history, evidence trail, shared data models |
| `supabase/` | Auth settings, branded email templates, sign-up limits migration |
| `docs/` | Technical notes for each subsystem |
| `tests/` | Automated tests |

## Security

- **The app stays locked without a login.** The web app only renders after Supabase confirms a valid session (`getUser()` checks the token with Supabase rather than trusting what's in the browser). If the config or the Supabase library can't load, the app shows an error instead of opening. Every `/api/` call needs a valid token, otherwise it gets `401`. A production server without Supabase configured refuses API calls (`503`) instead of running unprotected.
- **Sign-up rules**, enforced in the browser *and* by Supabase:
  - name: 2–50 characters, letters only (spaces, dots, apostrophes, hyphens allowed)
  - email: a complete address, at most 254 characters, with hints for typos like `gmial.com`
  - password: 8–72 characters with an uppercase letter, a lowercase letter, a number and a special character
  - Name and email are also checked by a database trigger (`supabase/migrations/`).
- **Rate limits**
  - Browser: 5 wrong passwords, then a lockout of 30s that doubles each time, up to 15 minutes.
  - Supabase: 20 sign-in/sign-up attempts per 5 minutes per IP, and 60 seconds between confirmation or reset emails.
  - API, per IP: 240 requests a minute, and 30 a minute without a valid token.
  - API, per user: 180 requests a minute, 10 checks a minute (60 an hour), 20 "Ask" questions a minute, 60 other changes (POST/DELETE) a minute.
  - Over the limit you get `429` with a `Retry-After` header.
  - Notes are capped at 2,000 characters and questions at 500.
- **Forgot password**: Supabase emails a reset link. It opens a "Set a new password" screen with the same password rules, and Supabase emails a notice when the password changes. The reply looks the same whether or not the email has an account, so nobody can use it to find out which emails are registered.
- **Supabase settings** live in `supabase/config.toml` and are applied with `supabase config push`. Branded email templates are in `supabase/templates/`. On the free plan they need a custom SMTP provider (for example Resend or SendGrid) before Supabase will use them, and that also raises Supabase's default limit of a few emails per hour.

## Run it locally

You need **Python 3.10+**.

```bash
git clone https://github.com/Itsmedexexplorer/Finsync.git
cd Finsync
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn backend.api.app:app --reload --port 8000
```

Open **http://localhost:8000**.

If you don't set any Supabase keys (and `VERITY_ENV` isn't `production`), FinSync runs in **local mode**: there's no sign-in screen and a single workspace stored in `data/verity.db`. That's the quickest way to try it.

### Turn on sign-in (Supabase)

1. Create a free project at [supabase.com](https://supabase.com).
2. Go to **Project Settings → API** and copy the *Project URL*, the *anon public* key and the *service_role* key.
3. Copy `.env.example` to `.env` and fill them in:
   ```bash
   SUPABASE_URL=https://xxxx.supabase.co
   SUPABASE_ANON_KEY=eyJ...
   SUPABASE_SERVICE_ROLE_KEY=eyJ...
   ```
4. In **Authentication → URL Configuration**, set the *Site URL* to where the app runs (e.g. `http://localhost:8000` or your deployed URL).
5. Restart the server. You'll get the sign-in screen, and the private backup bucket is created on startup.

No database tables are needed: FinSync stores each user's workspace itself and uses Supabase only for accounts and backups.

### Run the tests

```bash
python -m pytest
```

All 417 tests pass.

## Deploy

### Render (free tier)

The repo includes a `render.yaml` blueprint. The live app runs at https://finsync-vv9c.onrender.com.

1. Push this project to your own GitHub repository.
2. In Render: **New → Blueprint**, then pick the repository.
3. When asked, enter `SUPABASE_URL`, `SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_ROLE_KEY`.
4. Deploy. Then add the Render URL as the *Site URL* and as a *Redirect URL* in Supabase → Authentication → URL Configuration (or edit `site_url` in `supabase/config.toml` and run `supabase config push`).

On the free plan the service sleeps after 15 minutes without traffic, so the first request after that takes about 30 seconds. User data isn't lost when it sleeps because it's restored from Supabase Storage.

### Anywhere with Docker

```bash
docker build -t finsync .
docker run -p 8000:8000 --env-file .env finsync
```

Run **a single instance**. Workspaces are cached on local disk and rate limits are kept in memory, so running several replicas behind a load balancer needs a shared volume and a shared rate-limit store.

## Configuration

All settings are environment variables; `.env.example` lists them with comments. The `VERITY_` prefix is kept from the codebase FinSync grew out of. The main ones:

| Variable | Default | Purpose |
|---|---|---|
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | empty | Turn on sign-in. Empty means local single-user mode |
| `SUPABASE_SERVICE_ROLE_KEY` | empty | Server-only. Turns on workspace backups to Supabase Storage |
| `VERITY_ENV` | `development` | `production` refuses API calls (`503`) if Supabase isn't configured |
| `VERITY_ENABLE_DOCS` | `true` | Interactive API docs at `/docs` (off on the live site) |
| `VERITY_ENABLE_DEMO` | `false` | Expose the built-in sample scenarios and benchmark API (for development only) |
| `VERITY_MAX_UPLOAD_MB` | `15` | Per-file upload limit |
| `VERITY_MAX_FILES_PER_CASE` | `20` | Files allowed in one check |
| `VERITY_BACKUP_BUCKET` | `workspaces` | Private Supabase Storage bucket for workspace backups |

## API

The web app uses a JSON API, which you can also call directly. With Supabase turned on, send `Authorization: Bearer <supabase access token>`.

| Method & path | Purpose |
|---|---|
| `POST /api/v1/cases/files` | Run a check on uploaded files (multipart `files`) |
| `POST /api/v1/cases/text` | Run a check on pasted text |
| `GET /api/v1/checks` | List your checks |
| `GET /api/v1/cases/{id}` | Full result for one check |
| `GET /api/v1/cases/{id}/report` | Structured report (JSON) for one check |
| `DELETE /api/v1/checks/{id}` | Delete a check |
| `GET /api/v1/counterparties` | People with paid/due totals |
| `POST /api/v1/cases/{id}/controller/explain` | Ask a question about a check |
| `GET/POST /api/v1/cases/{id}/review/...` | Review: start, note, decision, resolve, close, `audit`, `audit/verify` |
| `POST /api/v1/cases/{id}/actions/propose` | Draft a reminder, dispute notice, proof request or journal entry |
| `GET /health` | Health check (no token needed) |

With `VERITY_ENABLE_DOCS=true` the full interactive reference is at `/docs`.

---

FinSync reuses the reconciliation engine from VERITY, an earlier project of ours. Unlike VERITY, FinSync does not use AI.
