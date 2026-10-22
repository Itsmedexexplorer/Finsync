<p align="center">
  <img src="frontend/assets/logo.svg" width="72" alt="FinSync logo">
</p>

<h1 align="center">FinSync</h1>
<p align="center"><b>Know who has really paid you.</b></p>

<p align="center"><a href="https://finsync-vv9c.onrender.com">Live app</a></p>

---

## About

FinSync is a web app for small businesses and freelancers. It checks invoices, payment messages and screenshots against your **bank statement** and tells you, in plain words, which payments actually reached your account and how much is still due.

A WhatsApp message like "35,000 GPay kar diya" or a payment screenshot only shows that someone *says* they paid. FinSync treats the bank statement as the source of truth and checks every claim against it.

FinSync works entirely on fixed rules: the same files always give the same result, and every number can be traced back to a record.

## Features

- Upload a bank statement with invoices, chat exports or screenshots, or paste a message
- Automatic matching of each payment claim to a bank entry (by amount, date, UTR/reference, invoice number and who paid)
- A clear status for every check:

| Status | Meaning |
|---|---|
| **Matched** | The payment is in your bank statement for the right amount |
| **Part paid** | Some money arrived, but less than expected |
| **Mismatch** | Your records disagree with the bank |
| **No bank proof** | Someone says they paid, but there's no bank entry |
| **Unclear** | More than one bank entry could match |
| **Duplicate** | The same payment appears twice; it's counted once |
| **Unmatched** | A bank entry or bill with nothing to pair it with yet |

- Expected vs. received vs. still due for every check
- **Home dashboard**: totals (expected, confirmed in bank, still due), a payment-status chart, a collection progress bar and a table of recent reconciliations
- A simple question when something doesn't add up, so you can confirm what happened
- Ready-to-copy follow-ups: payment reminder, dispute notice, proof request, accounting entry
- **People** page with paid and due totals for each customer or vendor
- History log that can be verified to show nothing was edited
- Private account for every user, light and dark theme, works on phone and desktop

## Supported files

| File | Format |
|---|---|
| Bank statement | CSV (net-banking export or Razorpay settlement report) |
| Invoices | PDF with selectable text |
| Chats | TXT export, or paste a message |
| Payment screenshots | PNG / JPG (saved as proof that someone says they paid; the amount inside the image isn't read) |

Up to 20 files per check, 15 MB each.

## How to use

1. Sign up and sign in.
2. Click **New check** and upload your bank statement plus any invoices, chats or screenshots.
3. Read the result: status, amounts and anything that didn't add up.
4. If FinSync asks a question, pick the answer that fits.
5. Send a follow-up if money is still due, and track totals on the **People** page.

## Tech stack

| Part | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, FastAPI |
| Database | SQLite (one per user) |
| Sign-in and backups | Supabase Auth and Supabase Storage |
| Hosting | Render |
| Tests | pytest |

## Project structure

```
frontend/   web app (index.html, styles.css, app.js)
backend/    FastAPI server and the matching logic
supabase/   sign-in settings and email templates
tests/      automated tests
docs/       technical notes
```

## Run locally

You need **Python 3.10 or newer**.

```bash
git clone https://github.com/Itsmedexexplorer/Finsync.git
cd Finsync
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn backend.api.app:app --reload --port 8000
```

Open **http://localhost:8000**.

Without Supabase keys, the app runs in single-user mode with no sign-in screen. To turn on sign-in, copy `.env.example` to `.env` and add your Supabase project's `SUPABASE_URL`, `SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_ROLE_KEY`.

### Run the tests

```bash
python -m pytest
```

## Deploy

The repo includes a `render.yaml` file for [Render](https://render.com):

1. In Render, choose **New → Blueprint** and select this repository.
2. Enter the three Supabase keys when asked.
3. Deploy, then add the Render URL as the *Site URL* in Supabase → Authentication → URL Configuration.

It can also run with Docker:

```bash
docker build -t finsync .
docker run -p 8000:8000 --env-file .env finsync
```
.
.
