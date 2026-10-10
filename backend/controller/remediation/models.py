"""Domain and Schema models for VERITY Proactive Remediation & Actions (Day 19).

Strict Invariants:
1. NO AUTONOMOUS EXTERNAL ACTION: Output is strictly draft proposals pending human review.
2. FINANCIAL TRUTH IMMUTABILITY: Actions and journals consume, but NEVER modify, reconciliation truth.
3. GROUNDING: Every communication draft must be 100% grounded in deterministic facts.
4. BALANCED JOURNALS: Total Debits == Total Credits must hold mathematically.
5. EXPLICIT COA MAPPING: If no customer Chart of Accounts is configured, marked as requires_account_mapping=True.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RemediationActionType(str, Enum):
    """Classification of proactive remediation action."""
    VENDOR_DISPUTE_NOTICE = "VENDOR_DISPUTE_NOTICE"
    PAYMENT_FOLLOWUP_DRAFT = "PAYMENT_FOLLOWUP_DRAFT"
    MISSING_EVIDENCE_REQUEST = "MISSING_EVIDENCE_REQUEST"
    DRAFT_JOURNAL_VOUCHER = "DRAFT_JOURNAL_VOUCHER"
    INTERNAL_CONTROLLER_NOTE = "INTERNAL_CONTROLLER_NOTE"


class ActionApprovalStatus(str, Enum):
    """Lifecycle status of a proactive remediation proposal."""
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPORTED = "EXPORTED"
    CANCELLED = "CANCELLED"


class NoticeChannel(str, Enum):
    """Target communication medium for drafted notice."""
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    LETTER = "LETTER"
    PORTAL_MESSAGE = "PORTAL_MESSAGE"


class RemediationNoticeDraft(BaseModel):
    """A deterministic, fact-grounded communication draft for external counterparties."""
    draft_id: str = Field(..., description="Unique draft identifier")
    action_type: RemediationActionType = Field(...)
    channel: NoticeChannel = Field(default=NoticeChannel.EMAIL)
    recipient_name: str = Field(..., description="Canonical counterparty name")
    recipient_contact: Optional[str] = Field(default=None, description="Email or phone if known")
    subject: str = Field(..., description="Draft subject line")
    body: str = Field(..., description="Full text body of the notice grounded in verified facts")
    
    # Grounding & Verification Metadata
    cited_invoice_ids: List[str] = Field(default_factory=list, description="Referenced invoice/claim IDs")
    cited_utr_references: List[str] = Field(default_factory=list, description="Referenced bank UTR/RRNs")
    stated_expected_amount: Optional[float] = Field(default=None, description="Invoiced amount INR")
    stated_matched_amount: Optional[float] = Field(default=None, description="Verified paid amount INR")
    stated_disputed_amount: Optional[float] = Field(default=None, description="Disputed shortfall INR")
    grounding_verified: bool = Field(default=False, description="Whether all cited facts match truth")
    created_at: str = Field(default_factory=_utc_now_iso)


class JournalEntryLine(BaseModel):
    """A single debit or credit line within a double-entry journal voucher."""
    line_number: int = Field(..., ge=1)
    account_code: str = Field(..., description="Chart of accounts code or placeholder")
    account_name: str = Field(..., description="Account title, e.g., Vendor Clearing")
    debit_amount: float = Field(default=0.0, ge=0.0, description="Debit amount INR")
    credit_amount: float = Field(default=0.0, ge=0.0, description="Credit amount INR")
    narration: str = Field(default="", description="Line-level explanatory memo")


class DraftJournalVoucher(BaseModel):
    """A deterministic double-entry Draft Journal Voucher representing the financial resolution."""
    voucher_id: str = Field(..., description="Unique voucher identifier, e.g., JV-2026-001")
    case_id: str = Field(..., description="Target case ID")
    voucher_date: str = Field(default_factory=_utc_now_iso, description="Voucher effective date")
    voucher_type: str = Field(default="GENERAL_JOURNAL", description="VOUCHER category")
    is_draft: bool = Field(default=True, description="Strictly True — DRAFT JOURNAL VOUCHER")
    
    # Chart-of-Accounts Safety Flag
    requires_account_mapping: bool = Field(
        default=True,
        description="True if generic placeholder accounts are used and customer COA configuration is required"
    )
    coa_mapping_profile: str = Field(
        default="STANDARD_PLACEHOLDER_COA",
        description="Profile name or 'CUSTOM_CONFIGURED'"
    )
    
    # Double-entry lines
    lines: List[JournalEntryLine] = Field(default_factory=list, description="Double-entry line items")
    total_debits: float = Field(default=0.0, ge=0.0, description="Sum of debits")
    total_credits: float = Field(default=0.0, ge=0.0, description="Sum of credits")
    is_balanced: bool = Field(default=False, description="True if total_debits == total_credits")
    
    # Narrative & Lineage
    general_narration: str = Field(..., description="Comprehensive accounting narrative")
    deterministic_basis: Dict[str, Any] = Field(default_factory=dict, description="Reconciliation values driving amounts")
    provenance_hash: str = Field(..., description="SHA-256 fingerprint linking to reconciliation record")
    created_at: str = Field(default_factory=_utc_now_iso)


class RemediationAction(BaseModel):
    """An actionable remediation proposal requiring explicit human approval."""
    action_id: str = Field(..., description="Unique remediation action ID")
    case_id: str = Field(..., description="Parent case ID")
    action_type: RemediationActionType = Field(...)
    approval_status: ActionApprovalStatus = Field(default=ActionApprovalStatus.PENDING_APPROVAL)
    title: str = Field(..., description="Concise human-readable action title")
    summary: str = Field(..., description="Executive summary of why this action was proposed")
    
    # Payloads
    notice_draft: Optional[RemediationNoticeDraft] = Field(default=None)
    journal_voucher: Optional[DraftJournalVoucher] = Field(default=None)
    
    # Review & Approval Audit
    proposed_by: str = Field(default="AI_FINANCE_CONTROLLER", description="Originating agent or system")
    approved_by: Optional[str] = Field(default=None, description="Human reviewer who approved")
    approved_at: Optional[str] = Field(default=None)
    rejection_reason: Optional[str] = Field(default=None, description="Reason if rejected by human")
    rejection_notes: Optional[str] = Field(default=None)
    audit_event_id: Optional[str] = Field(default=None, description="Linked audit trail event ID")
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: str = Field(default_factory=_utc_now_iso)
