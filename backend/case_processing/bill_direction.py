"""Tells apart invoices you sent from bills you paid.

FinSync reads every invoice as one the user issued (money should come IN). But people
also upload bills from their own suppliers, which they paid (money went OUT). The bank
statement settles which one it is: when an invoice's UTR, or its vendor's name together
with the exact amount, appears only on money leaving the account, the invoice is a bill
the user paid. Such claims become EXPENSE_INCURRED, so they are checked against debits
instead of being flagged as "money moved the wrong way".

This is a fixed rule that runs after the files are read and before matching.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence

from backend.domain.claim import Claim, ClaimType
from backend.domain.transaction import Transaction, TransactionDirection
from backend.entity_resolution.normalizer import EntityNormalizer


def _norm(value: Optional[str]) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def _refs(claim: Claim) -> List[str]:
    meta = claim.metadata or {}
    values = [claim.reference_id_hint, meta.get("payment_reference"), meta.get("invoice_number")]
    out = []
    for v in values:
        n = _norm(v)
        if len(n) >= 6 and sum(ch.isdigit() for ch in n) >= 4 and n not in out:
            out.append(n)
    return out


def _txn_mentions_ref(txn: Transaction, refs: Sequence[str]) -> bool:
    ref = _norm(txn.bank_reference)
    narration = _norm(txn.narration)
    return any(r == ref or (r and r in narration) for r in refs)


def _name_tokens(name: Optional[str]) -> List[str]:
    return [t for t in EntityNormalizer.extract_core_name_tokens(name) if len(t) > 2]


def _txn_mentions_name(txn: Transaction, name: Optional[str]) -> bool:
    tokens = _name_tokens(name)
    if not tokens:
        return False
    hay = EntityNormalizer.normalize_name(
        " ".join(filter(None, [txn.narration, str((txn.metadata or {}).get("counterparty_hint") or "")]))
    )
    return all(t in hay for t in tokens)


def _vendor_names(claim: Claim) -> List[str]:
    meta = claim.metadata or {}
    return [n for n in (meta.get("party_issuer"), meta.get("party_vendor")) if n]


def _same_amount(txn: Transaction, amount: Optional[float]) -> bool:
    return amount is not None and abs(txn.amount - amount) < 0.01


def infer_paid_bills(claims: Iterable[Claim], transactions: Sequence[Transaction]) -> List[Claim]:
    """Returns the claims, with invoices that the bank shows as paid OUT turned into bills paid."""
    debits = [t for t in transactions if t.direction == TransactionDirection.DEBIT]
    credits = [t for t in transactions if t.direction == TransactionDirection.CREDIT]
    result: List[Claim] = []

    for claim in claims:
        if claim.claim_type != ClaimType.INVOICE_ISSUED or not debits:
            result.append(claim)
            continue

        refs = _refs(claim)
        evidence: List[Transaction] = []
        if refs:
            out_hits = [t for t in debits if _txn_mentions_ref(t, refs)]
            in_hits = [t for t in credits if _txn_mentions_ref(t, refs)]
            if out_hits and not in_hits:
                evidence = out_hits
        if not evidence:
            # No shared reference: the vendor named on the bill was paid exactly this amount,
            # and nobody paid the user that amount.
            vendors = _vendor_names(claim)
            out_hits = [
                t for t in debits
                if _same_amount(t, claim.claimed_amount) and any(_txn_mentions_name(t, v) for v in vendors)
            ]
            in_same_amount = [t for t in credits if _same_amount(t, claim.claimed_amount)]
            if out_hits and not in_same_amount:
                evidence = out_hits

        if not evidence:
            result.append(claim)
            continue

        vendors = _vendor_names(claim)
        payee = next((v for v in vendors if any(_txn_mentions_name(t, v) for t in evidence)), None)
        payee = payee or (vendors[0] if vendors else claim.counterparty_hint)
        result.append(claim.model_copy(update={
            "claim_type": ClaimType.EXPENSE_INCURRED,
            "counterparty_hint": payee,
            "metadata": {
                **(claim.metadata or {}),
                "bill_paid": True,
                "original_claim_type": ClaimType.INVOICE_ISSUED.value,
            },
        }))
    return result
