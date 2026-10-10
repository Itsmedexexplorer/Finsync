"""Fact Grounding and Double-Entry Invariant Validators (Day 19).

Strict Invariants:
1. Zero Hallucinated Numbers: Draft notices cannot cite amounts not present in ReconciliationResult.
2. Zero Hallucinated References: Invoice IDs and Bank UTRs cited must exist in authoritative case evidence.
3. Zero Unbalanced Journals: Double-entry debits must strictly equal credits (len >= 2).
4. Mandatory Draft Status: Journal vouchers must be labeled as is_draft=True.
"""

from __future__ import annotations

import re
from typing import List, Optional, Set, Tuple

from backend.controller.remediation.models import (
    DraftJournalVoucher,
    RemediationNoticeDraft,
)
from backend.reconciliation.result import ReconciliationResult
from backend.reporting.models import FinancialTruthReport


class RemediationValidator:
    """Validates remediation artifacts against authoritative deterministic truth."""

    @staticmethod
    def validate_notice_grounding(
        draft: RemediationNoticeDraft,
        recon: ReconciliationResult,
        report: Optional[FinancialTruthReport] = None,
    ) -> Tuple[bool, List[str]]:
        """Verifies that all monetary amounts, invoices, and UTR references cited in the draft match reconciliation truth."""
        errors: List[str] = []
        valid_amounts: Set[float] = set()
        valid_invoices: Set[str] = set()
        valid_utrs: Set[str] = set()

        # 1. Authoritative Amounts
        if recon.expected_amount is not None:
            valid_amounts.add(round(recon.expected_amount, 2))
        if recon.matched_amount is not None:
            valid_amounts.add(round(recon.matched_amount, 2))
        if recon.outstanding_amount is not None:
            valid_amounts.add(round(recon.outstanding_amount, 2))
        valid_amounts.add(0.0)

        # 2. Authoritative Invoices & UTRs from ReconciliationResult
        if recon.claim_ids:
            for cid in recon.claim_ids:
                valid_invoices.add(cid.strip().upper())
        if recon.transaction_ids:
            for tid in recon.transaction_ids:
                valid_utrs.add(tid.strip().upper())

        # 3. Authoritative Data from FinancialTruthReport
        if report:
            if report.claims_summary:
                for c in report.claims_summary:
                    if c.claimed_amount is not None:
                        valid_amounts.add(round(c.claimed_amount, 2))
                    if c.reference_id_hint:
                        valid_invoices.add(c.reference_id_hint.strip().upper())
                    if c.claim_id:
                        valid_invoices.add(c.claim_id.strip().upper())

            if report.transaction_summary:
                for t in report.transaction_summary:
                    valid_amounts.add(round(t.amount, 2))
                    if t.bank_reference:
                        valid_utrs.add(t.bank_reference.strip().upper())
                    if t.transaction_id:
                        valid_utrs.add(t.transaction_id.strip().upper())

            if report.contradiction_summary:
                for d in report.contradiction_summary:
                    if d.expected_value and d.observed_value:
                        try:
                            ev_f = round(float(d.expected_value), 2)
                            ov_f = round(float(d.observed_value), 2)
                            valid_amounts.add(ev_f)
                            valid_amounts.add(ov_f)
                            valid_amounts.add(round(abs(ev_f - ov_f), 2))
                        except (ValueError, TypeError):
                            pass

        def _is_grounded_amount(val: Optional[float]) -> bool:
            if val is None:
                return True
            r_val = round(val, 2)
            return any(abs(r_val - v) < 0.02 for v in valid_amounts)

        # Validate Stated Amounts
        if draft.stated_expected_amount is not None and not _is_grounded_amount(draft.stated_expected_amount):
            errors.append(f"Ungrounded expected amount in draft: INR {draft.stated_expected_amount:,.2f}")

        if draft.stated_matched_amount is not None and not _is_grounded_amount(draft.stated_matched_amount):
            errors.append(f"Ungrounded matched amount in draft: INR {draft.stated_matched_amount:,.2f}")

        if draft.stated_disputed_amount is not None and not _is_grounded_amount(draft.stated_disputed_amount):
            errors.append(f"Ungrounded disputed/outstanding amount in draft: INR {draft.stated_disputed_amount:,.2f}")

        # Validate Cited Invoices
        if draft.cited_invoice_ids:
            for inv in draft.cited_invoice_ids:
                if inv and inv.strip().upper() not in valid_invoices:
                    errors.append(f"Ungrounded invoice reference cited in draft: '{inv}'")

        # Validate Cited UTRs
        if draft.cited_utr_references:
            for utr in draft.cited_utr_references:
                if utr and utr != "N/A" and utr.strip().upper() not in valid_utrs:
                    errors.append(f"Ungrounded bank UTR reference cited in draft: '{utr}'")

        is_valid = len(errors) == 0
        return is_valid, errors

    @staticmethod
    def validate_journal_voucher(
        voucher: DraftJournalVoucher,
    ) -> Tuple[bool, List[str]]:
        """Verifies that journal voucher lines strictly balance and satisfy accounting invariants."""
        errors: List[str] = []

        if len(voucher.lines) < 2:
            errors.append("Journal voucher must have at least 2 double-entry lines.")

        total_dr = sum(line.debit_amount for line in voucher.lines)
        total_cr = sum(line.credit_amount for line in voucher.lines)

        if abs(total_dr - total_cr) > 0.001:
            errors.append(
                f"Double-entry imbalance: Total Debits (INR {total_dr:,.2f}) != Total Credits (INR {total_cr:,.2f})"
            )

        if not voucher.is_draft:
            errors.append("Journal voucher must explicitly be marked as is_draft=True.")

        is_valid = len(errors) == 0
        return is_valid, errors
