"""Simple read models for the web app: the user's checks, the people in them, and deletion."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, status

from backend.api.dependencies import get_case_store, get_portfolio_service, get_review_service

router = APIRouter(tags=["Web App"])


def _check_summary(result, created_at: str | None, review) -> Dict[str, Any]:
    report = result.report
    fs = result.financial_summary or {}
    recon = result.reconciliation
    name = report.entity_summary.canonical_name if report else None
    expected = recon.expected_amount if recon else fs.get("claimed_amount")
    matched = recon.matched_amount if recon else fs.get("matched_amount", 0.0)
    outstanding = recon.outstanding_amount if recon else fs.get("outstanding_amount", 0.0)
    if result.status == "CONTRADICTED":
        # The money is in the bank but disputed; only a genuine shortfall counts as "still due".
        outstanding = max(0.0, (expected or 0.0) - (matched or 0.0))
    return {
        "case_id": result.case_id,
        "title": report.title if report else result.case_id,
        "counterparty": name if name and not name.strip().lower().startswith("unknown") else None,
        "status": result.status,
        "confidence": result.confidence_score,
        "requires_review": bool(report and report.unresolved_items) or result.status not in ("CONFIRMED",),
        "review_status": review.status.value if review else None,
        "review_decision": review.decision.value if review and review.decision else None,
        "expected_amount": expected,
        "matched_amount": matched,
        "outstanding_amount": outstanding,
        "issues_count": len(report.contradiction_summary) if report else fs.get("discrepancies_count", 0),
        "files_count": fs.get("evidence_count", 0),
        "created_at": created_at or (report.created_at.isoformat() if report else None),
    }


def _all_checks() -> List[Dict[str, Any]]:
    store = get_case_store()
    review_svc = get_review_service()
    records = store.storage.list_cases(limit=1000)
    checks = []
    for rec in records:
        result = store.get_case(rec.case_id)
        if not result:
            continue
        created = rec.created_at.isoformat() if hasattr(rec.created_at, "isoformat") else rec.created_at
        checks.append(_check_summary(result, created, review_svc.get_review(rec.case_id)))
    checks.sort(key=lambda c: c["created_at"] or "", reverse=True)
    return checks


@router.get("/api/v1/checks")
def list_checks() -> List[Dict[str, Any]]:
    """All of the signed-in user's checks, newest first."""
    return _all_checks()


@router.get("/api/v1/counterparties")
def list_counterparties() -> List[Dict[str, Any]]:
    """Customers and vendors seen across the user's checks, with running totals."""
    people: Dict[str, Dict[str, Any]] = {}
    for c in _all_checks():
        name = c["counterparty"]
        if not name:
            continue
        key = name.strip().lower()
        p = people.setdefault(key, {
            "name": name, "checks": 0, "expected_amount": 0.0, "matched_amount": 0.0,
            "outstanding_amount": 0.0, "issues_count": 0, "case_ids": [], "last_seen": None,
        })
        p["checks"] += 1
        p["expected_amount"] += c["expected_amount"] or 0.0
        p["matched_amount"] += c["matched_amount"] or 0.0
        p["outstanding_amount"] += c["outstanding_amount"] or 0.0
        p["issues_count"] += c["issues_count"] or 0
        p["case_ids"].append(c["case_id"])
        if not p["last_seen"] or (c["created_at"] or "") > p["last_seen"]:
            p["last_seen"] = c["created_at"]
    return sorted(people.values(), key=lambda p: p["last_seen"] or "", reverse=True)


@router.delete("/api/v1/checks/{case_id}")
def delete_check(case_id: str) -> Dict[str, Any]:
    """Permanently removes a check from the user's workspace."""
    store = get_case_store()
    if not store.get_case(case_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check not found.")
    store.storage.delete_case_if_allowed(case_id)

    review_svc = get_review_service()
    with review_svc._lock:
        review_svc._reviews.pop(case_id, None)
        review_svc._audit_chains.pop(case_id, None)

    portfolio = get_portfolio_service()
    with portfolio._lock:
        for d in (portfolio._cases, portfolio._raw_case_results,
                  portfolio._raw_controller_decisions, portfolio._raw_review_records):
            d.pop(case_id, None)
    return {"deleted": case_id}
