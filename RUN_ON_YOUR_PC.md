# Run FinSync on your PC

These steps start FinSync on your own computer at **http://localhost:8000**. Without Supabase
keys it runs in single-user mode: no sign-in screen, and your checks are saved in
`data/verity.db` on your PC.

## Windows

### 1. Install the tools (once)

1. **Python 3.10 or newer** – download from python.org. In the installer, tick
   **"Add python.exe to PATH"**.
2. **Tesseract OCR** (reads screenshots and photos) – download the Windows installer from the
   Tesseract project (the UB Mannheim build) and install it to the default folder
   `C:\Program Files\Tesseract-OCR`. FinSync finds it there on its own.

### 2. Open the project

Unzip the downloaded code, then open **Command Prompt** in the unzipped `Finsync` folder
(in File Explorer, click the address bar, type `cmd` and press Enter).

### 3. Set up (once)

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
```

### 4. Start FinSync

```bat
.venv\Scripts\activate
uvicorn backend.api.app:app --port 8000
```

Open **http://localhost:8000** in your browser. Press `Ctrl + C` in the Command Prompt to stop it.

## macOS

```bash
brew install python tesseract          # once
cd Finsync
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt     # once
uvicorn backend.api.app:app --port 8000
```

## Linux (Ubuntu / Debian)

```bash
sudo apt install python3 python3-venv tesseract-ocr     # once
cd Finsync
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt                      # once
uvicorn backend.api.app:app --port 8000
```

## Try it

Use the test kits (`FinSync_Test_Kit.zip` and `FinSync_Batch_Test_Kit.zip`): click **New check**,
add the bank statement and the screenshots, and click **Check payments**.

## Run the automated tests

```bash
python -m pytest
```

## Optional: sign-in like the live site

Copy `.env.example` to `.env` and fill in `SUPABASE_URL`, `SUPABASE_ANON_KEY` and
`SUPABASE_SERVICE_ROLE_KEY` from your Supabase project (Project Settings → API). In Supabase,
add `http://localhost:8000/**` under Authentication → URL Configuration → Redirect URLs.

## If something goes wrong

| Problem | Fix |
|---|---|
| `python` is not recognised | Reinstall Python with "Add python.exe to PATH" ticked, then open a new Command Prompt. |
| Screenshots are kept but amounts are not read | Tesseract is not installed, or is in another folder. Install it, or put `TESSERACT_CMD=C:\path\to\tesseract.exe` in a `.env` file. |
| Port 8000 is busy | Use another port: `uvicorn backend.api.app:app --port 8080`, then open http://localhost:8080. |
| `pip install` fails on Windows | Run `python -m pip install --upgrade pip`, then install again. |
