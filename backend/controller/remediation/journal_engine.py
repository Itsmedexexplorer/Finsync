"""Deterministic Double-Entry Draft Journal Voucher Engine (Day 19).

Strict Accounting Invariants:
1. TOTAL DEBITS == TOTAL CREDITS: Enforced mathematically on every generated voucher.
2. DRAFT STATUS: Every output is explicitly labeled as a DRAFT JOURNAL VOUCHER.
3. CONFIGURABLE COA: Accepts optional custom Chart of Accounts mapping.
4. UNCONFIGURED SAFETY: If no custom COA is provided, sets requires_account_mapping=True.
5. IMMUTABLE PROVENANCE: Every voucher includes SHA-256 fingerprint of the source reconciliation record.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Dict, List, Optional

from backend.controller.remediation.models import (
    DraftJournalVoucher,
    JournalEntryLine,
)
from backend.domain.reconciliation import ReconciliationStatus
from backend.reconciliation.result import ReconciliationResult
from backend.reporting.models import FinancialTruthReport


class JournalBalanceError(Exception):
    """Raised when double-entry debits do not strictly equal credits."""
    pass


class DraftJournalEngine:
    """Deterministic double-entry draft journal voucher engine."""

    # Default standardized placeholder account mapping (marked as requires_account_mapping=True)
    DEFAULT_PLACEHOLDER_COA = {
        "bank_clearing": {"code": "1100-CLEARING", "name": "Bank / Razorpay Clearing Account (Placeholder)"},
        "vendor_payable": {"code": "2100-AP-VENDOR", "name": "Accounts Payable / Vendor Clearing (Placeholder)"},
        "customer_receivable": {"code": "1200-AR-CUST", "name": "Accounts Receivable / Customer Clearing (Placeholder)"},
        "unapplied_debit": {"code": "1190-UNAPPLIED", "name": "Unapplied Advance / Shortfall Clearing (Placeholder)"},
        "reconciliation_suspense": {"code": "9999-SUSPENSE", "name": "Reconciliation Dispute Suspense Account (Placeholder)"},
    }

    @classmethod
    def generate_draft_voucher(
        cls,
        case_id: str,
        recon: ReconciliationResult,
        report: Optional[FinancialTruthReport] = None,
        custom_coa_mapping: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> DraftJournalVoucher:
        """Generates a balanced Draft Journal Voucher strictly from reconciliation outputs."""
        # 1. Determine COA configuration state
        if custom_coa_mapping:
            coa = {**cls.DEFAULT_PLACEHOLDER_COA, **custom_coa_mapping}
            requires_mapping = False
            profile_name = "CUSTOM_CONFIGURED_COA"
        else:
            coa = cls.DEFAULT_PLACEHOLDER_COA
            requires_mapping = True
            profile_name = "STANDARD_PLACEHOLDER_COA"

        entity_name = report.entity_summary.canonical_name if (report and report.entity_summary) else "Counterparty"
        expected = float(recon.expected_amount or 0.0)
        matched = float(recon.matched_amount or 0.0)
        outstanding = float(recon.outstanding_amount or 0.0)
        status = recon.status

        # 2. Extract Bank References / UTRs
        utrs = []
        if report and report.transaction_summary:
            for t in report.transaction_summary:
                if t.bank_reference:
                    utrs.append(t.bank_reference)
        utr_ref = ", ".join(utrs) if utrs else "N/A"

        lines: List[JournalEntryLine] = []

        # 3. Deterministic Accounting Entry Generation based on status
        if status == ReconciliationStatus.CONFIRMED:
            # Clean 1:1 Full Settlement
            # DR Vendor Payable / CR Bank Clearing for Matched Amount
            amt = matched if matched > 0 else expected
            lines.append(JournalEntryLine(
                line_number=1,
                account_code=coa["vendor_payable"]["code"],
                account_name=f"{coa['vendor_payable']['name']} — {entity_name}",
                debit_amount=amt,
                credit_amount=0.0,
                narration=f"Settlement of reconciled obligation for {entity_name}",
            ))
            lines.append(JournalEntryLine(
                line_number=2,
                account_code=coa["bank_clearing"]["code"],
                account_name=coa["bank_clearing"]["name"],
                debit_amount=0.0,
                credit_amount=amt,
                narration=f"Bank ledger disbursement / credit ref: {utr_ref}",
            ))
            narration = f"DRAFT: Settlement entry for Case {case_id} — {entity_name} (Fully Reconciled: INR {amt:,.2f})"

        elif status in (ReconciliationStatus.PARTIAL, ReconciliationStatus.PARTIALLY_SETTLED):
            # Partial Settlement
            # DR Vendor Payable (Matched Amount)
            # DR Unapplied Advance / Shortfall Clearing (Outstanding Amount)
            # CR Bank / Gateway Clearing (Total Claimed / Invoiced Amount)
            total_obligation = matched + outstanding if (matched + outstanding) > 0 else expected
            lines.append(JournalEntryLine(
                line_number=1,
                account_code=coa["vendor_payable"]["code"],
                account_name=f"{coa['vendor_payable']['name']} — {entity_name}",
                debit_amount=matched,
                credit_amount=0.0,
                narration=f"Verified partial settlement for {entity_name}",
            ))
            lines.append(JournalEntryLine(
                line_number=2,
                account_code=coa["unapplied_debit"]["code"],
                account_name=coa["unapplied_debit"]["name"],
                debit_amount=outstanding,
                credit_amount=0.0,
                narration=f"Unsettled balance allocated to pending vendor clearing",
            ))
            lines.append(JournalEntryLine(
                line_number=3,
                account_code=coa["bank_clearing"]["code"],
                account_name=coa["bank_clearing"]["name"],
                debit_amount=0.0,
                credit_amount=total_obligation,
                narration=f"Obligation posting ref: {utr_ref} (Matched: INR {matched:,.2f}, Due: INR {outstanding:,.2f})",
            ))
            narration = f"DRAFT: Partial settlement allocation for Case {case_id} — {entity_name} (Matched: INR {matched:,.2f}, Outstanding: INR {outstanding:,.2f})"

        elif status == ReconciliationStatus.CONTRADICTED:
            # Contradicted Dispute Entry
            # DR Reconciliation Suspense Account (Total Disputed Amount)
            # CR Vendor Payable / Disputed Liability (Total Disputed Amount)
            dispute_amt = expected if expected > 0 else (matched or 1000.0)
            lines.append(JournalEntryLine(
                line_number=1,
                account_code=coa["reconciliation_suspense"]["code"],
                account_name=coa["reconciliation_suspense"]["name"],
                debit_amount=dispute_amt,
                credit_amount=0.0,
                narration=f"Pending resolution of detected contradiction/discrepancy for Case {case_id}",
            ))
            lines.append(JournalEntryLine(
                line_number=2,
                account_code=coa["vendor_payable"]["code"],
                account_name=f"{coa['vendor_payable']['name']} — {entity_name} (Disputed)",
                debit_amount=0.0,
                credit_amount=dispute_amt,
                narration=f"Disputed invoice claim withheld pending counterparty response",
            ))
            narration = f"DRAFT: Suspense allocation for Contradicted Case {case_id} — {entity_name} (Disputed: INR {dispute_amt:,.2f})"

        else:
            # Default / Unverifiable / Ambiguous case
            # DR Reconciliation Suspense / CR Vendor Clearing
            amt = expected or matched or 0.0
            lines.append(JournalEntryLine(
                line_number=1,
                account_code=coa["reconciliation_suspense"]["code"],
                account_name=coa["reconciliation_suspense"]["name"],
                debit_amount=amt,
                credit_amount=0.0,
                narration=f"Unverified transaction hold for Case {case_id}",
            ))
            lines.append(JournalEntryLine(
                line_number=2,
                account_code=coa["vendor_payable"]["code"],
                account_name=f"{coa['vendor_payable']['name']} (Unverified)",
                debit_amount=0.0,
                credit_amount=amt,
                narration=f"Held in suspense pending verification documents",
            ))
            narration = f"DRAFT: Unverified transaction hold for Case {case_id} — {entity_name} (Amount: INR {amt:,.2f})"

        # 4. Strict Double-Entry Balance Calculation & Verification
        total_dr = sum(l.debit_amount for l in lines)
        total_cr = sum(l.credit_amount for l in lines)

        is_balanced = abs(total_dr - total_cr) < 0.001
        if not is_balanced:
            raise JournalBalanceError(
                f"Generated journal voucher is mathematically unbalanced: Total Debits (INR {total_dr:,.2f}) != Total Credits (INR {total_cr:,.2f})"
            )

        # 5. Provenance Fingerprint
        raw_seed = f"{case_id}|{recon.reconciliation_id}|{total_dr}|{total_cr}|{status.value}"
        provenance_hash = hashlib.sha256(raw_seed.encode("utf-8")).hexdigest()

        voucher_id = f"JV-{case_id}-{uuid.uuid4().hex[:6].upper()}"

        return DraftJournalVoucher(
            voucher_id=voucher_id,
            case_id=case_id,
            is_draft=True,
            requires_account_mapping=requires_mapping,
            coa_mapping_profile=profile_name,
            lines=lines,
            total_debits=total_dr,
            total_credits=total_cr,
            is_balanced=True,
            general_narration=narration,
            deterministic_basis={
                "reconciliation_id": recon.reconciliation_id,
                "status": status.value,
                "expected_amount": expected,
                "matched_amount": matched,
                "outstanding_amount": outstanding,
            },
            provenance_hash=provenance_hash,
        )
