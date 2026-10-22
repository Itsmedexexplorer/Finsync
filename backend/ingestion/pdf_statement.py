"""Reads bank statements that arrive as PDF files.

Two fixed-rule readers turn a statement's table into CSV text, which then goes through
the same BankCSVAdapter as an exported CSV, so every bank row is handled identically:

1. Column reader, for PDFs with real text. pypdf's layout mode keeps columns aligned,
   so the header row gives each column's position and every value is placed in the
   column it sits under. Wrapped narration lines are joined to their row.
2. Line reader, for text without reliable columns (for example OCR of a scanned
   statement). Each line that starts with a date and ends with amounts is a row; the
   running balance tells whether money came in or went out.
"""

from __future__ import annotations

import csv
import io
import re
from typing import List, Optional, Sequence, Tuple

from backend.ingestion.csv_adapter import BankCSVAdapter

_DATE = (
    r"(?:\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}[-\s](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*[-\s,]*\d{2,4})"
)
_DATE_RE = re.compile(rf"^{_DATE}$", re.IGNORECASE)
_DATE_AT_START = re.compile(rf"^\s*(?:\d{{1,4}}\s+)?(?P<date>{_DATE})\b", re.IGNORECASE)
_MONEY = r"\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?|\d+\.\d{2}"
_MONEY_RE = re.compile(rf"(?<![\w/.-])(?P<amt>{_MONEY})(?:\s*(?P<side>Cr|Dr|CR|DR))?(?![\w/])")
_REF_RE = re.compile(r"\b(?=[A-Z0-9]*\d{6,})[A-Z0-9]{10,24}\b")
_STATEMENT_WORDS = re.compile(
    r"\b(?:statement|account\s*(?:no|number|holder)|a/c|opening\s*balance|closing\s*balance)\b", re.IGNORECASE
)
_SKIP_LINE = re.compile(r"\b(?:opening|closing)\s*balance\b|\btotal\b|\bpage\s*\d+", re.IGNORECASE)
_OPENING = re.compile(rf"opening\s*balance\D{{0,20}}(?P<amt>{_MONEY})", re.IGNORECASE)

_MIN_ROWS = 2


def _cells(line: str) -> List[Tuple[int, int, str]]:
    """Text pieces separated by 2+ spaces, with their start and end columns."""
    return [(m.start(), m.end(), m.group(0)) for m in re.finditer(r"\S+(?: \S+)*", line)]


def _to_csv(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue()


def _amount(text: str) -> Optional[float]:
    try:
        return float(re.sub(r"[^\d.]", "", text))
    except ValueError:
        return None


# --- 1. Column reader ---------------------------------------------------------------

def _find_header(lines: List[str]) -> Optional[Tuple[int, List[Tuple[int, int, str]]]]:
    for idx, line in enumerate(lines):
        cells = _cells(line)
        if len(cells) < 3:
            continue
        fields = [BankCSVAdapter._classify_header(c[2]) for c in cells]
        if "date" in fields and any(f in fields for f in ("amount", "credit", "debit")):
            return idx, cells
    return None


def read_columns(text: str) -> Optional[str]:
    lines = text.splitlines()
    found = _find_header(lines)
    if not found:
        return None
    header_idx, header_cells = found
    header_text = [c[2] for c in header_cells]
    date_col = [BankCSVAdapter._classify_header(h) for h in header_text].index("date")
    text_cols = [
        i for i, h in enumerate(header_text)
        if BankCSVAdapter._classify_header(h) in ("narration", "counterparty")
    ]

    def column_for(start: int, end: int) -> int:
        best, best_gap = 0, None
        for i, (hs, he, _) in enumerate(header_cells):
            gap = 0 if (start < he + 1 and end > hs - 1) else min(abs(start - he), abs(end - hs))
            if best_gap is None or gap < best_gap:
                best, best_gap = i, gap
        return best

    rows: List[List[str]] = []
    for line in lines[header_idx + 1:]:
        if not line.strip():
            continue
        cells = _cells(line)
        if [c[2] for c in cells] == header_text:  # header repeated on a new page
            continue
        if _SKIP_LINE.search(line) and not _DATE_AT_START.match(line):
            continue
        values = [""] * len(header_cells)
        for start, end, piece in cells:
            col = column_for(start, end)
            values[col] = f"{values[col]} {piece}".strip()
        if _DATE_RE.match(values[date_col]):
            rows.append(values)
        elif rows and text_cols and not _MONEY_RE.search(line):
            # A wrapped narration line belongs to the row above it
            for col in range(len(values)):
                if values[col] and col in text_cols:
                    rows[-1][col] = f"{rows[-1][col]} {values[col]}".strip()
    rows = [r for r in rows if any(_MONEY_RE.search(v) for v in r)]
    if len(rows) < _MIN_ROWS:
        return None
    return _to_csv(header_text, rows)


# --- 2. Line reader -----------------------------------------------------------------

_CREDIT_WORDS = re.compile(r"\b(?:cr|credit|deposit|received|by\s+transfer|salary|refund|interest)\b", re.IGNORECASE)


def read_lines(text: str) -> Optional[str]:
    opening = _OPENING.search(text)
    prev_balance = _amount(opening.group("amt")) if opening else None
    rows: List[List[str]] = []
    for line in text.splitlines():
        m = _DATE_AT_START.match(line)
        if not m or _SKIP_LINE.search(line):
            continue
        rest = line[m.end():]
        money = list(_MONEY_RE.finditer(rest))
        if not money:
            continue
        balance = _amount(money[-1].group("amt")) if len(money) >= 2 else None
        amt_match = money[-2] if len(money) >= 2 else money[-1]
        amount = _amount(amt_match.group("amt"))
        if not amount:
            continue
        side = (amt_match.group("side") or "").upper()
        narration_part = rest[:money[0].start()]
        ref_m = _REF_RE.search(narration_part)
        reference = ref_m.group(0) if ref_m else ""
        narration = " ".join(narration_part.replace(reference, " ").split()) if reference else " ".join(narration_part.split())

        if side == "DR":
            is_credit = False
        elif side == "CR":
            is_credit = True
        elif prev_balance is not None and balance is not None:
            is_credit = abs(prev_balance + amount - balance) < 0.5
        else:
            is_credit = bool(_CREDIT_WORDS.search(narration_part))
        if balance is not None:
            prev_balance = balance
        rows.append([
            m.group("date"), narration, reference,
            "" if is_credit else f"{amount:.2f}", f"{amount:.2f}" if is_credit else "",
            f"{balance:.2f}" if balance is not None else "",
        ])
    if len(rows) < _MIN_ROWS:
        return None
    return _to_csv(["Date", "Narration", "Ref No", "Withdrawal", "Deposit", "Balance"], rows)


def looks_like_statement(text: str, source_name: str = "") -> bool:
    name = source_name.lower()
    return bool(_STATEMENT_WORDS.search(text)) or "statement" in name or "bank" in name or "passbook" in name


def statement_to_csv(layout_text: str, plain_text: str = "", source_name: str = "") -> Optional[str]:
    """CSV text for a bank statement, or None when the document is not one."""
    csv_text = read_columns(layout_text)
    if csv_text:
        return csv_text
    if looks_like_statement(plain_text or layout_text, source_name):
        return read_lines(layout_text) or (read_lines(plain_text) if plain_text else None)
    return None
