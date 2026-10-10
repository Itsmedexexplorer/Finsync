"""Generate Day 3 extraction sample fixtures."""

from pathlib import Path


def create_day3_samples() -> None:
    samples_dir = Path("data/samples/day3")
    samples_dir.mkdir(parents=True, exist_ok=True)

    # 1. Simple Payment Text
    (samples_dir / "simple_payment.txt").write_text(
        "Payment of ₹18,500 received from Rahul via UPI ref: 408219381920 on 2026-08-15.",
        encoding="utf-8"
    )

    # 2. Ambiguous Payment (No amount, no counterparty)
    (samples_dir / "ambiguous_payment.txt").write_text(
        "I sent the money yesterday.",
        encoding="utf-8"
    )

    # 3. Multilingual Messages
    multilingual_content = """1. Hinglish: Bhai 20k GPay kar diya check kar lo
2. Hindi: नमस्ते, मैंने बीस हज़ार रुपये गूगल पे कर दिए हैं। UTR: 408219381921
3. Marathi: काल 20 हजार पाठवले check करा
4. Tamil: GPay paniten 12500 check pannunga ref 408219381923
5. Telugu: GPay chesanu 22000 chusukondi ref 408219381927
6. Kannada: Hana kalsiddini 18000 PhonePe check maadi
7. Cash claim: Delivery boy ko cash de diya 10,000 pura
"""
    (samples_dir / "multilingual_messages.txt").write_text(multilingual_content, encoding="utf-8")

    # 4. Invoice Text
    (samples_dir / "invoice_text.txt").write_text(
        "TAX INVOICE #INV-2026-104\nBilled To: Bharat Tech Solutions Pvt Ltd\nDescription: Annual Cloud Support Retainer\nTotal Due: Rs. 48,000.00\nDue Date: 2026-08-30",
        encoding="utf-8"
    )

    # 5. Scanned notice
    (samples_dir / "scanned_notice.txt").write_text(
        "[SCANNED_PDF_DOCUMENT: sample_scanned_bill.pdf | Pages: 2 | Size: 102400 bytes]",
        encoding="utf-8"
    )

    print(f"Day 3 sample fixtures generated at {samples_dir.resolve()}")


if __name__ == "__main__":
    create_day3_samples()
