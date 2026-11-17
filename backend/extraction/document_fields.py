"""Shared rules for reading references and party names from documents and messages.

Used by the text extractor (messages, chats, OCR text) and the PDF extractor, so an
invoice reads the same whether it arrives as a PDF, a scan or a photo.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

# A payment reference worth matching against a bank statement has several digits:
# UPI RRNs are 12 digits, NEFT/RTGS/IMPS UTRs are 16-22 characters (e.g. UTIB2026102200482).
_MIN_REF_DIGITS = 6

_UTR_LABEL = re.compile(
    r"(?:\bUTR(?:\s*(?:No\.?|Number|#))?|\bRRN(?:\s*No\.?)?|UPI\s*(?:transaction|txn|ref(?:erence)?)\s*(?:ID|No\.?|Number)?"
    r"|\btransaction\s*(?:ID|No\.?|reference)|\btxn\s*(?:ID|No\.?|ref)|\bref(?:erence)?\s*(?:No\.?|Number|ID)?)"
    r"[ \t]*[:#\-]?\s*(?P<val>[A-Za-z0-9][A-Za-z0-9\-]{5,34})",
    re.IGNORECASE,
)

_INVOICE_LABEL = re.compile(
    r"(?:\binv(?:oice)?\.?|\bbill)[ \t]*(?:No\.?|Number|#|ID)?[ \t]*[:#\-]?[ \t]*(?P<val>[A-Za-z0-9][A-Za-z0-9/\-_]{2,30})",
    re.IGNORECASE,
)
_INVOICE_PATTERN = re.compile(r"\b(?:INV|BILL)[-_/]?[A-Z0-9/\-]*\d[A-Z0-9/\-]*\b", re.IGNORECASE)

_VENDOR_LABELS = r"vendor|supplier|seller|billed\s*by|issued\s*by|sold\s*by|service\s*provider|from"
_CLIENT_LABELS = r"client|customer|buyer|billed\s*to|bill\s*to|invoice\s*to|sold\s*to|recipient"
_PARTY_LINE = re.compile(
    rf"^[ \t]*(?P<label>{_VENDOR_LABELS}|{_CLIENT_LABELS})[ \t]*(?:name)?[ \t]*[:\-][ \t]*(?P<val>[^\n|]+)",
    re.IGNORECASE | re.MULTILINE,
)
_BUSINESS_WORDS = re.compile(
    r"\b(?:pvt|private|ltd|limited|llp|inc|corp|corporation|technologies|technology|enterprises|traders|trading"
    r"|solutions|industries|services|associates|agency|agencies|consultants|company|co\.|supplies|suppliers"
    r"|stores|store|mart|foods|hardware|motors|textiles|electricals|electronics|pharma|medicals|logistics"
    r"|works|studio|enterprise|distributors|exports|imports)\b",
    re.IGNORECASE,
)
_NOT_A_NAME = re.compile(r"\b(?:tax\s*invoice|invoice|receipt|statement|bill\s*of\s*supply|quotation)\b", re.IGNORECASE)


def _digits(value: str) -> int:
    """How many digits a text contains."""
    return sum(ch.isdigit() for ch in value)


def find_payment_reference(text: str) -> Optional[str]:
    """UTR / RRN / UPI or transaction reference, e.g. 'UTR No: UTIB2026102200482'.

    The value may sit on the next line (payment apps print the label above the number).
    Words such as 'INVOICE' are never returned: a reference needs at least six digits.
    """
    for m in _UTR_LABEL.finditer(text):
        val = _join_split_reference(m.group("val").strip("-"), text[m.end():])
        if _digits(val) >= _MIN_REF_DIGITS:
            return val
    return None


# A plain run of digits that ends the line or is followed by a space; never an amount
# such as "35,000" or "2500.00".
_NEXT_DIGIT_CHUNK = re.compile(r"^[ \t]+(\d{2,})(?=[ \t]*$|[ \t]+[^\d\s])", re.MULTILINE)


def _join_split_reference(val: str, rest: str) -> str:
    """OCR sometimes breaks a long reference with a space ("KKBKR576138 4146572"). Digit chunks
    that follow on the same line are joined back while the result still has a valid length:
    a NEFT/RTGS/IMPS UTR (letters first) is 16-22 characters, a UPI RRN is exactly 12 digits."""
    joined = val
    while True:
        m = _NEXT_DIGIT_CHUNK.match(rest)
        if not m:
            break
        candidate = joined + m.group(1)
        if joined[:1].isalpha() and len(candidate) <= 22:
            joined, rest = candidate, rest[m.end():]
        elif joined.isdigit() and len(joined) < 12 and len(candidate) <= 12:
            joined, rest = candidate, rest[m.end():]
        else:
            break
    if joined[:1].isalpha() and len(joined) < 16:
        return val
    if joined.isdigit() and len(joined) != 12 and joined != val:
        return val
    return joined


def find_invoice_number(text: str) -> Optional[str]:
    """Invoice or bill number on the same line as its label, e.g. 'Invoice No: INV-2026-0147'."""
    for m in _INVOICE_LABEL.finditer(text):
        val = m.group("val").strip("-/")
        if any(ch.isdigit() for ch in val) and val.lower() not in ("date",):
            return val
    m = _INVOICE_PATTERN.search(text)
    return m.group(0) if m else None


def _clean_name(value: str) -> Optional[str]:
    """Tidies a name read from a document; returns None when it is mostly digits or too short to be a name."""
    value = re.split(r"\s{2,}|\t", value.strip())[0]
    value = re.sub(r"[\s,;:.]+$", "", value).strip()
    if len(value) < 2 or _digits(value) > len(value) // 2:
        return None
    return value


def find_parties(text: str) -> Dict[str, str]:
    """Names on an invoice or receipt.

    Returns any of: 'vendor' (who issued the bill), 'client' (who it is billed to) and
    'issuer' (a business name printed as the letterhead on the first line).
    """
    parties: Dict[str, str] = {}
    for m in _PARTY_LINE.finditer(text):
        name = _clean_name(m.group("val"))
        if not name:
            continue
        label = re.sub(r"\s+", " ", m.group("label").lower())
        key = "client" if re.fullmatch(_CLIENT_LABELS, label, re.IGNORECASE) else "vendor"
        parties.setdefault(key, name)

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    is_bill = any(_NOT_A_NAME.search(ln) for ln in lines[:4])
    for line in lines[:1]:  # only the first non-empty line can be a letterhead
        if _NOT_A_NAME.search(line) or ":" in line or len(line) > 80:
            break
        # A short, letters-only first line on an invoice or receipt is the business that issued it.
        plain_name = is_bill and re.fullmatch(r"[A-Za-z][A-Za-z.&' ]{1,60}", line) and 1 <= len(line.split()) <= 6
        if (_BUSINESS_WORDS.search(line) or plain_name) and line.lower() != parties.get("client", "").lower():
            parties["issuer"] = line
    return parties
