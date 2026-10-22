"""End-to-end checks for bank statements in many shapes (CSV and PDF) and for
telling invoices you sent apart from bills you paid."""

from __future__ import annotations

import io
import os

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.extraction.ocr_extractor import ocr_available
from backend.ingestion.csv_adapter import BankCSVAdapter
from backend.ingestion.pdf_adapter import PDFDocumentAdapter

reportlab = pytest.importorskip("reportlab")
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _post(client: TestClient, *files):
    resp = client.post("/api/v1/cases/files", files=[("files", f) for f in files])
    assert resp.status_code == 200, resp.text
    return resp.json()


def _claims(data):
    return (data.get("truth_report") or {}).get("claims_summary", [])


def _text_pdf(lines_by_y, size=A4) -> bytes:
    """A real-text PDF; each item is (x, y, text, font_size)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=size)
    for x, y, text, fs in lines_by_y:
        c.setFont("Helvetica", fs)
        c.drawString(x, y, text)
    c.save()
    return buf.getvalue()


def _statement_pdf() -> bytes:
    """HDFC-style statement: preamble, Withdrawal / Deposit columns, a wrapped narration."""
    cols = [40, 105, 285, 385, 455, 525]
    items = [
        (40, 800, "HDFC BANK - Statement of Account", 12),
        (40, 784, "Account No: XXXXXX1234   Period: 01/08/2026 to 31/08/2026", 8),
        (cols[0], 750, "Txn Date", 8), (cols[1], 750, "Description", 8), (cols[2], 750, "Chq./Ref.No.", 8),
        (cols[3], 750, "Withdrawal Amt.", 8), (cols[4], 750, "Deposit Amt.", 8), (cols[5], 750, "Closing Balance", 8),
    ]
    rows = [
        ("15/08/2026", "UPI-RAMESH TRADERS-PAYMENT", "408219381920", "", "35,000.00", "1,85,000.00"),
        ("16/08/2026", "NEFT-POOJA PLASTICS PVT LTD", "NEFTN26235889012", "", "1,25,000.00", "3,10,000.00"),
        ("18/08/2026", "ATM WDL KORAMANGALA", "ATM0091823", "10,000.00", "", "3,00,000.00"),
    ]
    y = 730
    for row in rows:
        for x, val in zip(cols, row):
            if val:
                items.append((x, y, val, 8))
        y -= 14
    items.append((cols[1], y + 4, "INVOICE 0817 SETTLEMENT", 8))  # wrapped narration of the last row
    return _text_pdf(items)


# --- Bank statements ----------------------------------------------------------------

def test_csv_with_units_beneficiary_and_preamble():
    csv_text = (
        "SAMPLE BANK,Account statement\n"
        "Account holder: Sahaj,Period: Oct 2026\n"
        "#,Date,Mode,UTR / Ref No.,Beneficiary,Debit (INR),Balance (INR)\n"
        '1,13-10-2026,NEFT,UTIB2026102200482,Dhanesh Technologies Pvt Ltd,"1,00,000.00","5,51,450.00"\n'
    )
    res = BankCSVAdapter().ingest_payload(csv_text, source_name="s.csv")
    fields = res.evidence_items[0].metadata["normalized_fields"]
    assert fields["debit"] == "1,00,000.00"
    assert fields["reference"] == "UTIB2026102200482"
    assert fields["counterparty"] == "Dhanesh Technologies Pvt Ltd"


def test_amount_with_dr_cr_column(client):
    csv_text = b"Date,Particulars,Amount,Dr/Cr\n15/08/2026,UPI/408219381920/RAMESH,35000.00,CR\n16/08/2026,ATM WDL,5000.00,DR\n"
    data = _post(client, ("bank.csv", csv_text, "text/csv"), ("msg.txt", b"Ramesh: 35,000 GPay kar diya, ref 408219381920", "text/plain"))
    assert data["status"] == "CONFIRMED"
    assert data["financial_summary"]["matched_amount"] == 35000.0


def test_pdf_statement_with_withdrawal_and_deposit_columns():
    res = PDFDocumentAdapter().ingest_payload(_statement_pdf(), source_name="hdfc_statement.pdf")
    assert len(res.evidence_items) == 3
    rows = [e.metadata["normalized_fields"] for e in res.evidence_items]
    assert rows[0]["credit"] == "35,000.00" and rows[0]["reference"] == "408219381920"
    assert rows[1]["credit"] == "1,25,000.00"
    assert rows[2]["debit"] == "10,000.00"
    assert "SETTLEMENT" in rows[2]["narration"]  # wrapped line joined to its row


def test_pdf_statement_matches_a_message(client):
    data = _post(
        client,
        ("hdfc_statement.pdf", _statement_pdf(), "application/pdf"),
        ("chat.txt", b"Pooja Plastics: 1,25,000 NEFT kar diya, UTR NEFTN26235889012", "text/plain"),
    )
    assert data["status"] == "CONFIRMED"
    assert data["financial_summary"]["matched_amount"] == 125000.0
    assert data["financial_summary"]["transactions_count"] == 3


def test_ordinary_invoice_pdf_is_not_read_as_a_statement():
    pdf = _text_pdf([(40, 800, "TAX INVOICE", 14), (40, 780, "Invoice No: INV-2207", 10),
                     (40, 765, "Billed To: Pooja Plastics", 10), (40, 750, "Total Due: Rs. 1,50,000.00", 10)])
    res = PDFDocumentAdapter().ingest_payload(pdf, source_name="invoice.pdf")
    assert len(res.evidence_items) == 1
    assert res.evidence_items[0].source_type.value != "BANK_CSV"


@pytest.mark.skipif(not ocr_available() or not os.path.exists(FONT), reason="needs Tesseract and DejaVu font")
def test_scanned_pdf_statement_is_read_with_ocr():
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1400, 700), "white")
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 26)
    lines = [
        "SAMPLE BANK  Account Statement",
        "Opening Balance 8,50,000.00",
        "06-10-2026  NEFT RAMESH KULKARNI  HDFC52026588139986  62,000.00  7,88,000.00",
        "07-10-2026  UPI SALARY CREDIT  408219381920  12,000.00  8,00,000.00",
        "08-10-2026  NEFT AARAV TRADERS  SBIN52026753645568  2,750.00  7,97,250.00",
    ]
    for i, t in enumerate(lines):
        d.text((40, 40 + i * 70), t, fill="black", font=f)
    buf = io.BytesIO()
    img.save(buf, "PDF")
    res = PDFDocumentAdapter().ingest_payload(buf.getvalue(), source_name="scanned_statement.pdf")
    rows = [e.metadata["normalized_fields"] for e in res.evidence_items]
    assert len(rows) == 3
    assert rows[0]["debit"] == "62000.00"
    assert rows[1]["credit"] == "12000.00"  # balance went up
    assert rows[2]["debit"] == "2750.00"


# --- Invoices you sent vs bills you paid ----------------------------------------------

BILL = (
    "Dhanesh Technologies Private Limited\nTAX INVOICE\nInvoice No: INV-2026-0147\n"
    "Client: Sahaj and Dikshit\nTotal Amount: 1,00,000.00\nMode: NEFT\nUTR No: UTIB2026102200482\n"
)
DEBIT_CSV = (
    "Date,Mode,UTR / Ref No.,Beneficiary,Debit (INR),Balance (INR)\n"
    '13-10-2026,NEFT,UTIB2026102200482,Dhanesh Technologies Pvt Ltd,"{amt}","5,51,450.00"\n'
)


def test_bill_paid_by_utr_is_matched(client):
    data = _post(client, ("bank.csv", DEBIT_CSV.format(amt="1,00,000.00").encode(), "text/csv"),
                 ("bill.txt", BILL.encode(), "text/plain"))
    assert data["status"] == "CONFIRMED"
    fs = data["financial_summary"]
    assert fs["matched_amount"] == 100000.0 and fs["outstanding_amount"] == 0.0
    claim = _claims(data)[0]
    assert claim["claim_type"] == "EXPENSE_INCURRED"
    assert claim["reference_id_hint"] == "UTIB2026102200482"
    assert claim["counterparty_hint"] == "Dhanesh Technologies Private Limited"


def test_bill_part_paid_shows_balance_due(client):
    data = _post(client, ("bank.csv", DEBIT_CSV.format(amt="60,000.00").encode(), "text/csv"),
                 ("bill.txt", BILL.encode(), "text/plain"))
    fs = data["financial_summary"]
    assert data["status"] in ("PARTIAL", "PARTIALLY_SETTLED")
    assert fs["matched_amount"] == 60000.0 and fs["outstanding_amount"] == 40000.0


def test_bill_without_utr_matched_by_vendor_and_amount(client):
    bill = "Sunrise Enterprises\nTAX INVOICE\nInvoice No: SE-3341\nTotal Amount: Rs. 25,000.00\n"
    csv_text = (
        "Date,Narration,Ref No,Withdrawal,Deposit,Balance\n"
        "10-10-2026,NEFT/BARB52026576169871/SUNRISE ENTERPRISES,BARB52026576169871,25000.00,,722350.00\n"
    )
    data = _post(client, ("bank.csv", csv_text.encode(), "text/csv"), ("bill.txt", bill.encode(), "text/plain"))
    assert data["status"] == "CONFIRMED"
    assert _claims(data)[0]["claim_type"] == "EXPENSE_INCURRED"


def test_invoice_you_sent_and_customer_paid_stays_an_invoice(client):
    invoice = (
        "Sahaj Web Agency\nTAX INVOICE\nInvoice No: INV-0912\nBilled To: Pooja Plastics Pvt Ltd\n"
        "Total Amount: Rs. 1,25,000.00\nUTR No: NEFTN26235889012\n"
    )
    csv_text = (
        "Date,Narration,Chq/Ref No,Withdrawal,Deposit,Balance\n"
        "16/08/2026,NEFT/NEFTN26235889012/POOJAPLASTICS/ICICI,NEFTN26235889012,0.00,125000.00,310000.00\n"
    )
    data = _post(client, ("bank.csv", csv_text.encode(), "text/csv"), ("invoice.txt", invoice.encode(), "text/plain"))
    assert data["status"] == "CONFIRMED"
    claim = _claims(data)[0]
    assert claim["claim_type"] == "INVOICE_ISSUED"
    assert claim["counterparty_hint"] == "Pooja Plastics Pvt Ltd"


def test_word_invoice_is_never_a_reference():
    from backend.extraction.text_extractor import TextClaimExtractor

    assert TextClaimExtractor()._extract_reference_id("TAX INVOICE\nThanks for your business") is None
