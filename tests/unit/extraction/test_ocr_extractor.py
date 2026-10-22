"""Tests for OCR reading of screenshots, photographed receipts and scanned PDFs,
and for the stricter amount rules that OCR text relies on."""

from __future__ import annotations

import io
import os

import pytest
from PIL import Image, ImageDraw, ImageFont

from backend.extraction.ocr_extractor import (
    OCRExtractor,
    _fix_rupee_word,
    clean_ocr_text,
    looks_like_rupee,
    ocr_available,
)
from backend.extraction.service import ExtractionService
from backend.extraction.text_extractor import TextClaimExtractor
from backend.ingestion.image_adapter import ImagePaymentScreenshotAdapter
from backend.ingestion.pdf_adapter import PDFDocumentAdapter

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
needs_font = pytest.mark.skipif(not os.path.exists(FONT), reason="DejaVu Sans font not installed")
needs_ocr = pytest.mark.skipif(not ocr_available(), reason="Tesseract OCR not installed")


def _screenshot(lines, dark=False, width=720):
    bg, fg = ((18, 18, 20), (235, 235, 235)) if dark else ((255, 255, 255), (25, 25, 30))
    img = Image.new("RGB", (width, int(width * 1.5)), bg)
    draw = ImageDraw.Draw(img)
    y = 80
    for text, size in lines:
        draw.text((40, y), text, fill=fg, font=ImageFont.truetype(FONT, size))
        y += size + 34
    return img


def _png(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


GPAY = [("Paid to", 28), ("RAMESH TRADERS", 34), ("₹35,000", 72), ("Completed", 28),
        ("15 Aug 2026, 10:42 am", 26), ("UPI transaction ID", 24), ("408219381920", 28)]


# --- Amount rules (no OCR engine needed) -----------------------------------------

def test_indian_total_beats_invoice_number():
    text = "TAX INVOICE #INV-1058\nBilled To: Pooja Plastics\nTotal Due: Rs. 1,50,000.00\nDue Date: 2026-08-30"
    amount, _ = TextClaimExtractor()._extract_amount(text)
    assert amount == 150000.0


def test_reference_number_is_not_an_amount():
    amount, _ = TextClaimExtractor()._extract_amount("Ref 12345 paid ₹500 by UPI")
    assert amount == 500.0


def test_amount_glued_to_identifier_is_skipped():
    amount, _ = TextClaimExtractor()._extract_amount("Order A1058B settled, 2500 paid")
    assert amount == 2500.0


def test_plain_message_amount_still_read():
    amount, _ = TextClaimExtractor()._extract_amount("bhai 35000 gpay kar diya")
    assert amount == 35000.0


# --- Rupee-sign repair -------------------------------------------------------------

@pytest.mark.parametrize("word,expected", [
    ("%35,000", "₹35,000"),
    ("~1,25,000", "₹1,25,000"),
    ("¥8,500.00", "₹8,500.00"),
    ("235,000", "₹35,000"),      # impossible in Indian grouping without the sign
    ("41,25,000", "41,25,000"),   # valid Indian number: left alone without glyph proof
    ("408219381920", "408219381920"),
    ("#1058", "#1058"),
    ("₹35,000", "₹35,000"),
])
def test_fix_rupee_word(word, expected):
    assert _fix_rupee_word(word, None) == expected


def test_comma_read_as_space_is_repaired():
    assert clean_ocr_text("Paid\n₹1 25,000\nDone") == "Paid\n₹1,25,000\nDone"


@needs_font
def test_rupee_glyph_shape_is_recognised():
    font = ImageFont.truetype(FONT, 80)

    def glyph(ch):
        img = Image.new("L", (140, 140), 255)
        ImageDraw.Draw(img).text((20, 10), ch, fill=0, font=font)
        return img

    assert looks_like_rupee(glyph("₹"))
    for digit in "0123456789":
        assert not looks_like_rupee(glyph(digit)), digit


# --- OCR end to end ----------------------------------------------------------------

@needs_ocr
@needs_font
@pytest.mark.parametrize("dark", [False, True])
def test_screenshot_amount_is_read(dark):
    ingest = ImagePaymentScreenshotAdapter().ingest_payload(_png(_screenshot(GPAY, dark=dark)), source_name="gpay.png")
    evidence = ingest.evidence_items[0]
    result = ExtractionService().extract_from_evidence(evidence)
    assert result.claims, result.errors
    claim = result.claims[0]
    assert claim.claimed_amount == 35000.0
    assert claim.reference_id_hint == "408219381920"
    assert claim.metadata.get("read_by_ocr") is True
    assert result.provider_name.startswith("tesseract_ocr")


@needs_ocr
@needs_font
def test_photographed_receipt_is_read():
    lines = [("PAYMENT RECEIPT", 40), ("Received from: Cloud Fees", 28), ("Amount: Rs. 8,500.00", 30),
             ("Mode: GPay UPI", 26), ("Date: 19/08/2026", 26)]
    ingest = ImagePaymentScreenshotAdapter().ingest_payload(_png(_screenshot(lines, width=900)), source_name="receipt.jpg")
    result = ExtractionService().extract_from_evidence(ingest.evidence_items[0])
    assert result.claims and result.claims[0].claimed_amount == 8500.0


@needs_ocr
@needs_font
def test_scanned_pdf_invoice_is_read():
    lines = [("TAX INVOICE", 40), ("Invoice No: INV-2207", 28), ("Billed To: Pooja Plastics", 28),
             ("Total Due: Rs. 1,50,000.00", 30), ("Due Date: 2026-08-30", 26)]
    buf = io.BytesIO()
    _screenshot(lines, width=1000).save(buf, "PDF")
    ingest = PDFDocumentAdapter().ingest_payload(buf.getvalue(), source_name="scanned_invoice.pdf")
    evidence = ingest.evidence_items[0]
    assert evidence.metadata.get("is_scanned") is True
    result = ExtractionService().extract_from_evidence(evidence)
    assert result.claims, result.errors
    assert result.claims[0].claimed_amount == 150000.0
    assert result.claims[0].reference_id_hint == "INV-2207"


@needs_font
def test_ocr_switched_off_keeps_old_behaviour(monkeypatch):
    monkeypatch.setenv("VERITY_OCR_ENABLED", "false")
    assert not OCRExtractor().is_available()
    ingest = ImagePaymentScreenshotAdapter().ingest_payload(_png(_screenshot(GPAY)), source_name="gpay.png")
    result = ExtractionService().extract_from_evidence(ingest.evidence_items[0])
    assert all(c.claimed_amount is None for c in result.claims)
    assert not result.provider_name.startswith("tesseract_ocr")


@needs_ocr
def test_blank_image_falls_back_without_error():
    blank = Image.new("RGB", (400, 600), (255, 255, 255))
    ingest = ImagePaymentScreenshotAdapter().ingest_payload(_png(blank), source_name="blank.png")
    result = ExtractionService().extract_from_evidence(ingest.evidence_items[0])
    assert not result.provider_name.startswith("tesseract_ocr")
