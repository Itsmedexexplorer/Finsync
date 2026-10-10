<p align="center">
  <img src="frontend/assets/logo.svg" width="72" alt="Verity logo">
</p>

<h1 align="center">Verity</h1>
<p align="center"><b>Find out who has really paid you.</b><br>
Verity checks invoices, payment screenshots and WhatsApp messages against your bank statement and tells you, in plain words, what actually reached your account.</p>

---

## What is Verity?

Small businesses, agencies and freelancers in India get payment proof from all over the place:

- "Bhai 35,000 GPay kar diya, check kar lo" on WhatsApp
- A PhonePe or Paytm screenshot
- A PDF invoice from Zoho or Tally
- The bank statement, which is the only record that shows money actually arrived

A message or screenshot only shows that someone says they paid. Verity treats your **bank statement as the source of truth** and checks every claim against it.

For each check you get:

| You see | What it means |
|---|---|
| **Matched** | The payment is in your bank statement, for the right amount. |
| **Part paid** | Some money arrived, but less than what was billed or promised. |
| **Mismatch** | Your records disagree with the bank (amount, reference number, direction…). |
| **No bank proof** | Someone says they paid, but there's no matching bank entry. |
| **Unclear** | More than one bank entry could match, so you need to pick. |
| **Duplicate** | The same payment appears twice (e.g. screenshot + bank line). It's only counted once. |

Each check also shows **expected vs. received vs. still due**, a list of **what didn't add up**, **next steps**, and an **Ask** box where you can ask questions about the check in plain English. Answers come only from your own records.

## How to use it

1. **Sign up.** Every account gets its own private workspace, and it starts empty.
2. **Take the tour.** A short walkthrough opens on your first visit and points out each part of the app. You can replay it anytime from *How it works* or *Account*.
3. **Start a check.** Tap **New check** and add:
   - your **bank statement** (CSV export from net-banking or a Razorpay settlement report); this is the most important file
   - any **invoices** (PDF), **payment screenshots** (PNG/JPG) or **chat exports** (TXT). You can also paste a message.
4. **Read the verdict.** Verity reads the files, matches every claim to a bank entry and shows the result.
5. **Review.** If something doesn't add up, the check is flagged. Pick **Looks right**, **Something's wrong** or **Need more proof**, tick off the suggested tasks and add notes.
6. **Follow up.** Create a payment reminder, a dispute notice, a request for proof, or a draft accounting entry. Verity writes the draft from the facts in the check; you copy it and send it yourself.
7. **Track people.** The *People* page totals what each customer or vendor has paid and still owes across all your checks.

| Page | What it's for |
|---|---|
| **Home** | Totals: checks run, money confirmed in bank, still due, checks needing review |
| **New check** | Upload files or paste a message, then run the check |
| **Checks** | Every check with its verdict. Filter by *Needs review*, *Matched*, *Money due*, *Mismatch* |
| **Check details** | Verdict, amounts, issues, next steps, Ask, plus tabs for Records, Review, Follow-ups and History |
| **People** | Customers and vendors with paid/due totals |
| **How it works** | Status meanings, file types, FAQ, replay the tour |
| **Account** | Profile, change password, sign out |

The app is responsive: it has a bottom tab bar on phones and a sidebar on larger screens.

## How it works under the hood

```
Browser (frontend/)                     Server (backend/, FastAPI)
┌───────────────────────┐   HTTPS +     ┌──────────────────────────────────────────────┐
│ Plain HTML/CSS/JS app │  Supabase JWT │ Auth middleware → verifies the token with     │
│ • Supabase sign-in    │ ────────────▶ │   Supabase, opens that user's workspace       │
│ • Hash router         │               │                                              │
│ • Guided tour         │               │ Pipeline (per check)                         │
└───────────────────────┘               │  1 Ingest files (CSV, PDF, image, text)      │
                                        │  2 Extract claims; bank rows → transactions  │
                                        │  3 Resolve who's who (names, UPI, GSTIN, PAN)│
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

- **Rules do the maths.** Matching, amounts and statuses come from fixed rules, so the same input always gives the same answer. AI is optional and only helps read scanned documents. It never decides amounts.
- **Your data is kept separate.** Each user has their own workspace (`data/workspaces/<user-id>/`). Users can't see each other's checks or people.
- **Your data survives restarts.** Free hosting wipes the server's disk on every restart. After each change, Verity uploads a snapshot of your workspace to a private Supabase Storage bucket and restores it automatically the next time you sign in.
- **Uploaded files aren't kept.** They're written to a temp folder, processed and deleted. Only the results are stored.
- **History can't be changed quietly.** Review activity is hash-chained, and *History → Verify* checks that nothing was edited.

Main code locations:

| Path | What's there |
|---|---|
| `frontend/` | The whole web app: `index.html`, `styles.css`, `app.js`, logo/icons |
| `backend/api/` | FastAPI app, routes, auth middleware (`auth.py`), web-app endpoints (`user_routes.py`) |
| `backend/workspace.py` | Per-user workspaces |
| `backend/cloud_sync.py` | Backup/restore to Supabase Storage |
| `backend/case_processing/` | The 8-stage pipeline |
| `backend/ingestion`, `extraction`, `entity_resolution`, `transaction_matching`, `deduplication`, `contradiction_detection`, `reconciliation`, `reporting` | One folder per pipeline stage |
| `backend/review`, `backend/controller` | Review workflow, next-step suggestions, follow-up drafts and journal entries |
| `docs/` | Technical notes for each subsystem |
| `tests/` | 400+ automated tests |

## Run it locally

You need **Python 3.10+**.

```bash
git clone <your-repo-url> verity
cd verity
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn backend.api.app:app --reload --port 8000
```

Open **http://localhost:8000**.

If you don't set any Supabase keys, Verity runs in **local mode**: there's no sign-in screen and a single workspace stored in `data/verity.db`. That's the quickest way to try it.

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

No database tables are needed: Verity stores each user's workspace itself and uses Supabase only for accounts and backups.

### Run the tests

```bash
python -m pytest
```

## Deploy

### Render (recommended, free tier)

The repo includes a `render.yaml` blueprint.

1. Push this project to your own GitHub repository.
2. In Render: **New → Blueprint**, then pick the repository.
3. When asked, enter `SUPABASE_URL`, `SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_ROLE_KEY`.
4. Deploy. Then add the Render URL (e.g. `https://verity.onrender.com`) as the *Site URL* and as a *Redirect URL* in Supabase → Authentication → URL Configuration.

On the free plan the service sleeps after 15 minutes without traffic, so the first request after that takes about 30 seconds. User data isn't lost when it sleeps because it's restored from Supabase Storage.

### Anywhere with Docker

```bash
docker build -t verity .
docker run -p 8000:8000 --env-file .env verity
```

Run **a single instance**. Workspaces are cached on local disk, so running several replicas behind a load balancer needs a shared volume.

## Configuration

All settings are environment variables. `.env.example` lists them with comments. The main ones:

| Variable | Default | Purpose |
|---|---|---|
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | empty | Turn on sign-in. Empty means local single-user mode |
| `SUPABASE_SERVICE_ROLE_KEY` | empty | Server-only. Turns on workspace backups to Supabase Storage |
| `VERITY_ENABLE_DEMO` | `false` | Expose the built-in sample scenarios and benchmark API (for development only) |
| `VERITY_ENABLE_DOCS` | `true` | Interactive API docs at `/docs` |
| `VERITY_MAX_UPLOAD_MB` | `15` | Per-file upload limit |
| `VERITY_AI_PROVIDER` | `MOCK` | `GEMINI` turns on AI reading of scanned documents (needs `GEMINI_API_KEY`) |

## API

The web app uses a JSON API, which you can also call directly. With Supabase turned on, send `Authorization: Bearer <supabase access token>`.

| Method & path | Purpose |
|---|---|
| `POST /api/v1/cases/files` | Run a check on uploaded files (multipart `files`) |
| `GET /api/v1/checks` | List your checks |
| `GET /api/v1/cases/{id}` | Full result for one check |
| `DELETE /api/v1/checks/{id}` | Delete a check |
| `GET /api/v1/counterparties` | People with paid/due totals |
| `POST /api/v1/cases/{id}/controller/explain` | Ask a question about a check |
| `GET/POST /api/v1/cases/{id}/review/...` | Review: start, note, decision, resolve, close, audit, verify |
| `POST /api/v1/cases/{id}/actions/propose` | Draft a reminder, dispute notice, proof request or journal entry |

With `VERITY_ENABLE_DOCS=true` the full interactive reference is at `/docs`.

---

Verity started as an entry for the Razorpay AI Buildathon 2026 (AI Finance Controller track).
