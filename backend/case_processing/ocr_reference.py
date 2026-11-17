"""Corrects one-character OCR slips in payment references.

Reading a photo can add, drop or swap a single character in a long UTR
("PUNBR57915645049" read as "PUNBR5S7915645049"). A reference that came from OCR and is
not in the bank statement is replaced by a statement reference only when:

* it is at least 11 characters long (a 12-digit UPI RRN with one digit lost still counts),
* exactly one statement reference is within one character edit of it, and
* that statement reference is also at least 12 characters long.

Typed text is never changed: a typed reference that is not in the bank stays as it is.
This is a fixed rule that runs after the files are read and before matching.
"""

from __future__ import annotations

import re
from typing import List, Optional, Sequence

from backend.domain.claim import Claim
from backend.domain.transaction import Transaction

_MIN_LEN = 12        # bank references: UPI RRNs are 12 digits, NEFT/RTGS UTRs 16-22
_MIN_OCR_LEN = 11    # what was read from the photo, which may have lost one character


def _norm(value: Optional[str]) -> str:
    """Upper case, letters and digits only, so references compare reliably."""
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def _within_one_edit(a: str, b: str) -> bool:
    """True when a and b differ by at most one inserted, deleted or replaced character."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    for i in range(len(long_)):
        if long_[:i] + long_[i + 1:] == short:
            return True
    return False


def snap_ocr_references(claims: Sequence[Claim], transactions: Sequence[Transaction]) -> List[Claim]:
    """Replaces a reference read from a photo with the bank's reference when they differ by one character and only one bank line is that close. Typed text is never changed."""
    bank_refs = {_norm(t.bank_reference): t.bank_reference for t in transactions if len(_norm(t.bank_reference)) >= _MIN_LEN}
    out: List[Claim] = []
    for claim in claims:
        meta = claim.metadata or {}
        ref = _norm(claim.reference_id_hint)
        if not meta.get("read_by_ocr") or len(ref) < _MIN_OCR_LEN or ref in bank_refs:
            out.append(claim)
            continue
        near = [raw for n, raw in bank_refs.items() if _within_one_edit(ref, n)]
        if len(near) != 1:
            out.append(claim)
            continue
        fixed = near[0]
        new_meta = {**meta, "ocr_reference_read_as": claim.reference_id_hint}
        if _norm(meta.get("payment_reference")) == ref:
            new_meta["payment_reference"] = fixed
        out.append(claim.model_copy(update={"reference_id_hint": fixed, "metadata": new_meta}))
    return out
