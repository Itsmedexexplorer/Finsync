"""Test fixture generator for Day 17 multimodal extraction tests.

Creates real PNG, JPEG, and PDF test fixtures that exercise the actual
image/PDF processing pipeline (not text placeholders).
"""

import io
import json
import os
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw, ImageFont
import pypdf
from pypdf import PdfWriter


def create_upi_screenshot(output_path: Path) -> None:
    """Create a realistic UPI payment screenshot as PNG."""
    img = Image.new("RGB", (400, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Header
    draw.rectangle([(0, 0), (400, 80)], fill=(75, 0, 130))
    draw.text((120, 25), "UPI Payment", fill=(255, 255, 255))

    # Payment details
    draw.text((30, 100), "Payment Successful", fill=(0, 128, 0))
    draw.text((30, 140), "Amount: Rs. 25,000.00", fill=(0, 0, 0))
    draw.text((30, 170), "To: Ramesh Kumar", fill=(0, 0, 0))
    draw.text((30, 200), "UPI Ref: 408219381920", fill=(100, 100, 100))
    draw.text((30, 230), "Date: 23/08/2026", fill=(100, 100, 100))
    draw.text((30, 260), "From: HDFC A/c XX1234", fill=(100, 100, 100))
    draw.text((30, 300), "Status: SUCCESS", fill=(0, 128, 0))

    img.save(output_path, format="PNG")
    print(f"  Created UPI screenshot: {output_path}")


def create_bank_screenshot(output_path: Path) -> None:
    """Create a bank transaction screenshot as JPEG."""
    img = Image.new("RGB", (500, 400), color=(245, 245, 245))
    draw = ImageDraw.Draw(img)

    draw.rectangle([(0, 0), (500, 60)], fill=(0, 51, 102))
    draw.text((150, 18), "Bank Statement", fill=(255, 255, 255))

    draw.text((20, 80), "Date: 22/08/2026", fill=(0, 0, 0))
    draw.text((20, 110), "Description: UPI/408219381920/RAMESH", fill=(0, 0, 0))
    draw.text((20, 140), "Debit: Rs 25,000.00", fill=(200, 0, 0))
    draw.text((20, 170), "Balance: Rs 1,45,230.50", fill=(0, 0, 0))

    img.save(output_path, format="JPEG", quality=85)
    print(f"  Created bank screenshot: {output_path}")


def create_invoice_image(output_path: Path) -> None:
    """Create an invoice image as PNG."""
    img = Image.new("RGB", (500, 700), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    draw.text((180, 20), "TAX INVOICE", fill=(0, 0, 0))
    draw.text((30, 60), "Invoice No: INV-2026-088", fill=(0, 0, 0))
    draw.text((30, 90), "Date: 20/08/2026", fill=(0, 0, 0))
    draw.text((30, 130), "Billed To:", fill=(0, 0, 0))
    draw.text((30, 155), "Creative Minds Studio", fill=(0, 0, 0))
    draw.text((30, 185), "GSTIN: 27AABCU9603R1ZP", fill=(100, 100, 100))
    draw.line([(30, 220), (470, 220)], fill=(0, 0, 0))
    draw.text((30, 240), "Description", fill=(0, 0, 0))
    draw.text((350, 240), "Amount", fill=(0, 0, 0))
    draw.line([(30, 265), (470, 265)], fill=(200, 200, 200))
    draw.text((30, 280), "UI/UX Design Services", fill=(0, 0, 0))
    draw.text((350, 280), "Rs 30,000", fill=(0, 0, 0))
    draw.text((30, 310), "CGST (9%)", fill=(0, 0, 0))
    draw.text((350, 310), "Rs 2,700", fill=(0, 0, 0))
    draw.text((30, 340), "SGST (9%)", fill=(0, 0, 0))
    draw.text((350, 340), "Rs 2,700", fill=(0, 0, 0))
    draw.line([(30, 370), (470, 370)], fill=(0, 0, 0))
    draw.text((30, 385), "Total Due:", fill=(0, 0, 0))
    draw.text((330, 385), "Rs 35,400.00", fill=(0, 0, 0))

    img.save(output_path, format="PNG")
    print(f"  Created invoice image: {output_path}")


def create_scanned_pdf(output_path: Path) -> None:
    """Create a PDF containing an embedded image (simulating a scanned document)."""
    # Create a receipt-like image
    img = Image.new("RGB", (600, 800), color=(250, 248, 240))
    draw = ImageDraw.Draw(img)

    draw.text((200, 30), "RECEIPT", fill=(0, 0, 0))
    draw.text((50, 80), "Receipt No: RCP-2026-445", fill=(0, 0, 0))
    draw.text((50, 110), "Date: 21/08/2026", fill=(0, 0, 0))
    draw.text((50, 150), "Received From: Priya Sharma", fill=(0, 0, 0))
    draw.text((50, 190), "Amount: Rs 18,500.00", fill=(0, 0, 0))
    draw.text((50, 220), "Payment Mode: NEFT", fill=(0, 0, 0))
    draw.text((50, 250), "Ref: NEFTN26235889012", fill=(0, 0, 0))
    draw.text((50, 300), "For: Consulting Services July 2026", fill=(0, 0, 0))
    draw.text((50, 350), "Signature: _______________", fill=(0, 0, 0))

    # Save as temporary PNG
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    img_buf.seek(0)

    # Build a PDF with the image embedded (this creates a genuinely scanned-like PDF)
    writer = PdfWriter()

    # Create a blank page and add image using pypdf
    # Since pypdf doesn't easily create image-only PDFs, we'll use a simpler approach:
    # Create a PDF with reportlab-like minimal structure
    from pypdf.generic import (
        ArrayObject,
        DictionaryObject,
        NameObject,
        NumberObject,
        StreamObject,
    )

    # Simpler approach: create minimal valid PDF with image
    _create_image_pdf(output_path, img_buf.getvalue())
    print(f"  Created scanned PDF: {output_path}")


def _create_image_pdf(output_path: Path, png_bytes: bytes) -> None:
    """Create a minimal PDF containing only an embedded image (no selectable text)."""
    # Use PIL to convert to a PDF directly — this creates an image-only PDF
    img = Image.open(io.BytesIO(png_bytes))
    img.save(str(output_path), "PDF", resolution=100.0)


def create_multipage_scanned_pdf(output_path: Path) -> None:
    """Create a multi-page scanned PDF with images on each page."""
    pages = []

    # Page 1: Invoice header
    img1 = Image.new("RGB", (600, 800), color=(255, 255, 255))
    draw1 = ImageDraw.Draw(img1)
    draw1.text((200, 30), "INVOICE", fill=(0, 0, 0))
    draw1.text((50, 80), "Invoice: INV-MP-001", fill=(0, 0, 0))
    draw1.text((50, 110), "Date: 15/08/2026", fill=(0, 0, 0))
    draw1.text((50, 150), "Client: Omega Tech Solutions", fill=(0, 0, 0))
    draw1.text((50, 190), "Page 1 of 2", fill=(100, 100, 100))
    pages.append(img1)

    # Page 2: Itemized details
    img2 = Image.new("RGB", (600, 800), color=(255, 255, 255))
    draw2 = ImageDraw.Draw(img2)
    draw2.text((50, 30), "INVOICE DETAILS (continued)", fill=(0, 0, 0))
    draw2.text((50, 80), "Item: Software Development", fill=(0, 0, 0))
    draw2.text((50, 110), "Amount: Rs 2,50,000.00", fill=(0, 0, 0))
    draw2.text((50, 140), "GST (18%): Rs 45,000.00", fill=(0, 0, 0))
    draw2.text((50, 170), "Total Due: Rs 2,95,000.00", fill=(0, 0, 0))
    draw2.text((50, 210), "Page 2 of 2", fill=(100, 100, 100))
    pages.append(img2)

    # Save as multi-page PDF
    pages[0].save(
        str(output_path),
        "PDF",
        resolution=100.0,
        save_all=True,
        append_images=pages[1:],
    )
    print(f"  Created multi-page scanned PDF: {output_path}")


def main() -> None:
    """Generate all Day 17 test fixtures."""
    fixture_dir = Path("data/samples/day17/fixtures")
    fixture_dir.mkdir(parents=True, exist_ok=True)

    print("Generating Day 17 test fixtures...")
    create_upi_screenshot(fixture_dir / "upi_payment_screenshot.png")
    create_bank_screenshot(fixture_dir / "bank_transaction_screenshot.jpg")
    create_invoice_image(fixture_dir / "invoice_image.png")
    create_scanned_pdf(fixture_dir / "scanned_receipt.pdf")
    create_multipage_scanned_pdf(fixture_dir / "multipage_scanned_invoice.pdf")

    print(f"\nAll fixtures created in {fixture_dir}/")


if __name__ == "__main__":
    main()
