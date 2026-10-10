"""Generate Day 2 sample files across Bank CSV, WhatsApp text, PDF, and Image modalities."""

from pathlib import Path
from PIL import Image, ImageDraw


def generate_minimal_text_pdf(text_lines: list[str]) -> bytes:
    """Generate a valid standard PDF byte stream containing text."""
    # Build text stream
    stream_content = "BT\n/F1 12 Tf\n50 750 Td\n"
    for line in text_lines:
        safe_line = line.replace("(", "\\(").replace(")", "\\)")
        stream_content += f"({safe_line}) Tj\n0 -20 Td\n"
    stream_content += "ET\n"
    stream_bytes = stream_content.encode("latin-1")

    objects = [
        b"",  # 0
        b"<< /Type /Catalog /Pages 2 0 R >>",  # 1
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",  # 2
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",  # 3
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",  # 4
        f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("latin-1") + stream_bytes + b"endstream",  # 5
    ]

    pdf = b"%PDF-1.4\n"
    xref_offsets = [0]
    for i in range(1, len(objects)):
        xref_offsets.append(len(pdf))
        pdf += f"{i} 0 obj\n".encode("latin-1") + objects[i] + b"\nendobj\n"

    start_xref = len(pdf)
    pdf += f"xref\n0 {len(objects)}\n0000000000 65535 f \n".encode("latin-1")
    for offset in xref_offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode("latin-1")

    pdf += f"trailer\n<< /Size {len(objects)} /Root 1 0 R >>\nstartxref\n{start_xref}\n%%EOF\n".encode("latin-1")
    return pdf


def create_samples() -> None:
    samples_dir = Path("data/samples/day2")
    samples_dir.mkdir(parents=True, exist_ok=True)

    # 1. Bank Statement CSV (Valid)
    csv_content = """Date,Narration,Chq/Ref No,Withdrawal,Deposit,Balance
15/08/2026,UPI/408219381920/PAYTO/RAMESH/HDFC/002341,408219381920,0.00,35000.00,185000.00
16/08/2026,NEFT/NEFTN26235889012/POOJAPLASTICS/ICICI,NEFTN26235889012,0.00,125000.00,310000.00
17/08/2026,UPI/419082390192/DESIGNRETAINER/PAYTM,419082390192,0.00,24000.00,334000.00
18/08/2026,ATM/WDL/KORAMANGALA/CASH,ATM0091823,10000.00,0.00,324000.00
19/08/2026,UPI/420918390182/CLOUDFEES/GPAY,420918390182,0.00,8500.00,332500.00
"""
    (samples_dir / "bank_statement.csv").write_text(csv_content, encoding="utf-8")

    # 2. Malformed Statement CSV (Partial Success demo)
    malformed_csv = """Date,Narration,Amount,Ref
15/08/2026,Valid Row 1,10000.00,REF101
16/08/2026,Malformed Row with too many columns,20000.00,REF102,EXTRA_COLUMN_HERE
17/08/2026,Valid Row 3,30000.00,REF103
18/08/2026
19/08/2026,Valid Row 5,50000.00,REF105
"""
    (samples_dir / "malformed_statement.csv").write_text(malformed_csv, encoding="utf-8")

    # 3. WhatsApp Messages TXT
    whatsapp_content = """[15/08/2026, 11:20:10] Ramesh Sharma: Bhai 35,000 GPay kar diya check kar lo
[15/08/2026, 11:22:45] You: Thanks Rameshji, received Rs 35,000. Invoice marked paid.
[16/08/2026, 14:05:00] Pooja Plastics: Sent Rs 1,25,000 via NEFT for polymer supply batch #42.
[17/08/2026, 18:30:12] Vikram: Namaste, maine 15000 google pay kar diye hain. UTR: 408219381920
[18/08/2026, 09:15:30] Client Ananya: Remaining 20k agle hafte bhej dunga pakka.
"""
    (samples_dir / "whatsapp_messages.txt").write_text(whatsapp_content, encoding="utf-8")

    # 4. Sample Invoice PDF (Valid text PDF)
    pdf_bytes = generate_minimal_text_pdf([
        "TAX INVOICE #INV-2026-088",
        "Billed To: Creative Minds Design Studio",
        "Description: UI/UX Retainer Services August 2026",
        "Amount Due: Rs. 35,000.00",
        "Due Date: 2026-08-25",
    ])
    (samples_dir / "sample_invoice.pdf").write_bytes(pdf_bytes)

    # 5. Payment Screenshot PNG
    img_path = samples_dir / "payment_screenshot.png"
    img = Image.new("RGB", (600, 400), color=(245, 247, 250))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 580, 380], outline=(79, 70, 229), width=3)
    draw.text((40, 50), "Google Pay - Payment Successful", fill=(30, 41, 59))
    draw.text((40, 100), "Paid to: Rohit Verma (rohit@okhdfcbank)", fill=(30, 41, 59))
    draw.text((40, 150), "Amount: Rs. 35,000.00", fill=(16, 185, 129))
    draw.text((40, 200), "UPI Ref: 408219381920", fill=(71, 85, 105))
    draw.text((40, 250), "Date: 15 Aug 2026, 11:15 AM", fill=(71, 85, 105))
    img.save(img_path, format="PNG")

    print(f"Sample files successfully generated in {samples_dir.resolve()}")


if __name__ == "__main__":
    create_samples()
