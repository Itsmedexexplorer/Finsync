"""One upload, many payments.

When the user uploads a bank statement together with many screenshots, invoices or chats in
a single go, this module reads every file once, splits the payment claims into separate
payments, and runs each payment through the normal pipeline on its own, against the same
bank statement. Each payment becomes its own check, so its result is exactly what a
separate upload of that payment would give.

How claims are grouped into payments (fixed rules):
1. Claims that share a payment reference (UTR / UPI ID / invoice number) are one payment,
   so two screenshots of the same transfer, or a screenshot and a chat about it, stay together.
2. A claim without a reference joins a payment from the same person for the same amount, if
   there is exactly one; otherwise claims without a reference are grouped by the person's name.
3. A claim with neither a reference nor a name is a payment on its own.
Bank statement rows are never claims; every payment is checked against all of them.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from backend.case_processing.bill_direction import infer_paid_bills
from backend.case_processing.models import CaseInput
from backend.case_processing.ocr_reference import snap_ocr_references
from backend.domain.claim import Claim
from backend.domain.evidence import Evidence, EvidenceModality
from backend.domain.transaction import Transaction


def _norm_ref(value: Optional[str]) -> str:
    """A reference in a comparable form: upper case, letters and digits only."""
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def _norm_name(value: Optional[str]) -> str:
    """A person or business name in a comparable form: lower case, no punctuation, no 'Pvt Ltd' style words."""
    v = re.sub(r"[^a-z0-9 ]", " ", (value or "").lower())
    v = re.sub(r"\b(?:m s|ms|mr|mrs|shri|pvt|private|ltd|limited|llp|the)\b", " ", v)
    return " ".join(v.split())


def _refs_of(claim: Claim) -> List[str]:
    """The payment references (UTR / UPI id) a claim carries, in comparable form."""
    meta = claim.metadata or {}
    out: List[str] = []
    for v in (claim.reference_id_hint, meta.get("payment_reference")):
        n = _norm_ref(v)
        if len(n) >= 6 and sum(ch.isdigit() for ch in n) >= 4 and n not in out:
            out.append(n)
    return out


@dataclass
class PaymentGroup:
    """One payment found in an upload: the claims about it and the files they came from."""
    claims: List[Claim] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)


@dataclass
class BatchPlan:
    """Everything read from one upload: bank statement rows, the payments found, and files nothing could be read from."""
    bank_evidence: List[Evidence]
    transactions: List[Transaction]
    groups: List[PaymentGroup]
    unread_files: List[str]
    warnings: List[str]


def plan_batch(pipeline, file_paths: List[str]) -> BatchPlan:
    """Reads every file once and splits the claims into separate payments."""
    from backend.case_processing.pipeline import _bank_claim_to_transaction

    evidence: List[Evidence] = []
    warnings: List[str] = []
    for fp in file_paths:
        res = pipeline.ingestion_service.ingest_file(fp)
        if res.evidence_items:
            evidence.extend(res.evidence_items)
        elif res.errors:
            warnings.extend(e.message for e in res.errors)

    bank_ids = {ev.id for ev in evidence if ev.modality == EvidenceModality.BANK_STATEMENT}
    claims: List[Claim] = []
    txns: List[Transaction] = []
    claims_by_ev: Dict[str, int] = {}
    for ev in evidence:
        ext = pipeline.extraction_service.extract_from_evidence(ev)
        for c in ext.claims or []:
            txn = _bank_claim_to_transaction(c) if ev.id in bank_ids else None
            if txn is not None:
                txns.append(txn)
            elif ev.id not in bank_ids:
                claims.append(c)
                claims_by_ev[ev.id] = claims_by_ev.get(ev.id, 0) + 1

    # Same corrections the pipeline applies before matching.
    claims = snap_ocr_references(claims, txns)
    claims = infer_paid_bills(claims, txns)

    # --- group claims into payments (union-find over shared keys) ---
    parent = list(range(len(claims)))

    def find(i: int) -> int:
        """Union-find: the representative claim of the group claim i belongs to."""
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        """Union-find: puts the groups of claims a and b together (they are the same payment)."""
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    by_ref: Dict[str, int] = {}
    for i, c in enumerate(claims):
        for r in _refs_of(c):
            if r in by_ref:
                union(by_ref[r], i)
            else:
                by_ref[r] = i

    with_ref = [i for i, c in enumerate(claims) if _refs_of(c)]
    by_name: Dict[str, int] = {}
    for i, c in enumerate(claims):
        if _refs_of(c):
            continue
        name = _norm_name(c.counterparty_hint)
        if not name:
            continue  # rule 3: a payment on its own
        same_payment = [
            j for j in with_ref
            if _norm_name(claims[j].counterparty_hint) == name
            and c.claimed_amount is not None and claims[j].claimed_amount == c.claimed_amount
        ]
        roots = {find(j) for j in same_payment}
        if len(roots) == 1:
            union(roots.pop(), i)
        elif name in by_name:
            union(by_name[name], i)
        else:
            by_name[name] = i

    ev_by_id = {ev.id: ev for ev in evidence}
    groups_by_root: Dict[int, PaymentGroup] = {}
    for i, c in enumerate(claims):
        g = groups_by_root.setdefault(find(i), PaymentGroup())
        g.claims.append(c)
        ev = ev_by_id.get(c.evidence_id)
        if ev is not None and ev not in g.evidence:
            g.evidence.append(ev)

    # Files that produced no claim at all (for example an unreadable photo) are reported.
    unread = [
        ev.source_name or ev.id for ev in evidence
        if ev.id not in bank_ids and ev.id not in claims_by_ev
    ]

    groups = sorted(groups_by_root.values(), key=lambda g: min(claims.index(c) for c in g.claims))
    return BatchPlan(
        bank_evidence=[ev for ev in evidence if ev.id in bank_ids],
        transactions=txns,
        groups=groups,
        unread_files=unread,
        warnings=warnings,
    )


def case_input_for(plan: BatchPlan, group: PaymentGroup, case_id: str, batch_meta: Dict) -> CaseInput:
    """A normal case for one payment: its own proof plus the whole bank statement."""
    return CaseInput(
        case_id=case_id,
        evidence_items=list(group.evidence) + list(plan.bank_evidence),
        transactions=list(plan.transactions),
        metadata={
            "precomputed_claims": [c.model_dump(mode="json") for c in group.claims],
            **batch_meta,
        },
    )


def new_batch_id() -> str:
    """A new id for one upload, e.g. BATCH-1a2b3c4d; its checks are BATCH-1a2b3c4d-01, -02 ..."""
    return f"BATCH-{uuid.uuid4().hex[:8]}"


def _describe(narration: Optional[str]) -> str:
    """A readable description from a statement narration (which may hold the whole CSV row)."""
    text = (narration or "").strip()
    if text.count(",") >= 3:
        fields = [f.strip() for f in text.split(",")]
        wordy = [f for f in fields if re.search(r"[A-Za-z]{3,}", f)]
        if wordy:
            text = max(wordy, key=len)
    return text[:120]


def unexplained_bank_lines(plan: BatchPlan, used_txn_ids: set, maybe_for: Optional[Dict[str, str]] = None) -> List[Dict]:
    """Bank entries that none of the uploaded proofs accounts for.

    maybe_for maps a bank line to the person whose check could not decide between lines
    (an 'Unclear' check), so the user knows where to resolve it."""
    maybe_for = maybe_for or {}
    out: List[Dict] = []
    for t in plan.transactions:
        if t.id in used_txn_ids:
            continue
        out.append({
            "date": t.known_timestamp.isoformat() if t.known_timestamp else None,
            "amount": t.amount,
            "direction": t.direction.value if hasattr(t.direction, "value") else str(t.direction),
            "reference": t.bank_reference,
            "description": _describe(t.narration),
            "maybe_for": maybe_for.get(t.id),
        })
    return out
