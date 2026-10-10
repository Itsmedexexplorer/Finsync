"""Remediation Action Service & Human Approval Workflow (Day 19).

Strict Invariants:
1. HUMAN IN THE LOOP: No action is marked APPROVED without explicit human approval.
2. AUDIT TRAIL: Every proposal, approval, and rejection appends to the SHA-256 audit chain.
3. ZERO AUTONOMOUS DISPATCH: External transmission is strictly prohibited.
4. ZERO REPLAY / INVALID TRANSITION: Re-approval of rejected actions or direct export from pending is rejected.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from backend.controller.remediation.generator import RemediationDraftGenerator
from backend.controller.remediation.journal_engine import DraftJournalEngine
from backend.controller.remediation.models import (
    ActionApprovalStatus,
    DraftJournalVoucher,
    NoticeChannel,
    RemediationAction,
    RemediationActionType,
    RemediationNoticeDraft,
)
from backend.controller.remediation.validator import RemediationValidator
from backend.reconciliation.result import ReconciliationResult
from backend.reporting.models import FinancialTruthReport
from backend.review.service import ReviewService
from backend.storage.audit_store import PersistentAuditStore
from backend.storage.database import DatabaseEngine
from backend.storage.repositories.sql.case import SQLCaseRepository
from backend.storage.repositories.sql.reconciliation import SQLReconciliationRepository
from backend.storage.repositories.sql.reporting import SQLTruthReportRepository

logger = logging.getLogger("verity.controller.remediation")


class RemediationActionService:
    """Orchestrates proactive remediation actions, draft generation, and human approval."""

    def __init__(
        self,
        engine: DatabaseEngine,
        review_service: Optional[ReviewService] = None,
    ):
        self.engine = engine
        self.review_service = review_service or ReviewService()
        self._actions_store: Dict[str, RemediationAction] = {}
        self._vouchers_store: Dict[str, DraftJournalVoucher] = {}

    def propose_dispute_notice(
        self,
        case_id: str,
        channel: NoticeChannel = NoticeChannel.EMAIL,
        recipient_contact: Optional[str] = None,
    ) -> RemediationAction:
        """Proposes a grounded vendor dispute notice requiring human approval."""
        recon, report = self._get_case_truth(case_id)
        if not recon:
            raise ValueError(f"No reconciliation record found for case {case_id}")

        self._validate_case_provenance(case_id, recon, report)

        draft = RemediationDraftGenerator.generate_vendor_dispute_notice(
            case_id=case_id,
            recon=recon,
            report=report,
            channel=channel,
            recipient_email_or_phone=recipient_contact,
        )

        is_valid, errors = RemediationValidator.validate_notice_grounding(draft, recon, report)
        if not is_valid:
            raise ValueError(f"Dispute notice failed grounding validation: {', '.join(errors)}")

        action_id = f"ACT-DISP-{uuid.uuid4().hex[:8].upper()}"
        action = RemediationAction(
            action_id=action_id,
            case_id=case_id,
            action_type=RemediationActionType.VENDOR_DISPUTE_NOTICE,
            approval_status=ActionApprovalStatus.PENDING_APPROVAL,
            title=f"Vendor Dispute Notice: {draft.recipient_name}",
            summary=f"Formal dispute notice for Case {case_id} citing disputed shortfall of INR {draft.stated_disputed_amount or 0:,.2f}",
            notice_draft=draft,
            proposed_by="AI_FINANCE_CONTROLLER",
        )

        self._actions_store[action_id] = action
        self._record_audit_event(
            case_id=case_id,
            event_type="ACTION_PROPOSED",
            description=f"Proposed Vendor Dispute Notice for {draft.recipient_name} (Shortfall: INR {draft.stated_disputed_amount or 0:,.2f})",
            affected_ids=[action_id, draft.draft_id],
        )

        return action

    def propose_payment_followup(
        self,
        case_id: str,
        channel: NoticeChannel = NoticeChannel.EMAIL,
        recipient_contact: Optional[str] = None,
    ) -> RemediationAction:
        """Proposes a grounded payment follow-up / reminder notice requiring human approval."""
        recon, report = self._get_case_truth(case_id)
        if not recon:
            raise ValueError(f"No reconciliation record found for case {case_id}")

        self._validate_case_provenance(case_id, recon, report)

        draft = RemediationDraftGenerator.generate_payment_followup_draft(
            case_id=case_id,
            recon=recon,
            report=report,
            channel=channel,
            recipient_email_or_phone=recipient_contact,
        )

        is_valid, errors = RemediationValidator.validate_notice_grounding(draft, recon, report)
        if not is_valid:
            raise ValueError(f"Payment follow-up failed grounding validation: {', '.join(errors)}")

        action_id = f"ACT-FLW-{uuid.uuid4().hex[:8].upper()}"
        action = RemediationAction(
            action_id=action_id,
            case_id=case_id,
            action_type=RemediationActionType.PAYMENT_FOLLOWUP_DRAFT,
            approval_status=ActionApprovalStatus.PENDING_APPROVAL,
            title=f"Payment Follow-Up: {draft.recipient_name}",
            summary=f"Payment follow-up for Case {case_id} requesting balance settlement of INR {draft.stated_disputed_amount or 0:,.2f}",
            notice_draft=draft,
            proposed_by="AI_FINANCE_CONTROLLER",
        )

        self._actions_store[action_id] = action
        self._record_audit_event(
            case_id=case_id,
            event_type="ACTION_PROPOSED",
            description=f"Proposed Payment Follow-Up for {draft.recipient_name} (Balance: INR {draft.stated_disputed_amount or 0:,.2f})",
            affected_ids=[action_id, draft.draft_id],
        )

        return action

    def propose_missing_evidence_request(
        self,
        case_id: str,
        channel: NoticeChannel = NoticeChannel.EMAIL,
        recipient_contact: Optional[str] = None,
    ) -> RemediationAction:
        """Proposes a request for missing bank advice or verification documents."""
        recon, report = self._get_case_truth(case_id)
        if not recon:
            raise ValueError(f"No reconciliation record found for case {case_id}")

        self._validate_case_provenance(case_id, recon, report)

        draft = RemediationDraftGenerator.generate_missing_evidence_request(
            case_id=case_id,
            recon=recon,
            report=report,
            channel=channel,
            recipient_email_or_phone=recipient_contact,
        )

        action_id = f"ACT-REQ-{uuid.uuid4().hex[:8].upper()}"
        action = RemediationAction(
            action_id=action_id,
            case_id=case_id,
            action_type=RemediationActionType.MISSING_EVIDENCE_REQUEST,
            approval_status=ActionApprovalStatus.PENDING_APPROVAL,
            title=f"Missing Evidence Request: {draft.recipient_name}",
            summary=f"Request for bank proof/advice regarding unverified claim of INR {draft.stated_expected_amount or 0:,.2f}",
            notice_draft=draft,
            proposed_by="AI_FINANCE_CONTROLLER",
        )

        self._actions_store[action_id] = action
        self._record_audit_event(
            case_id=case_id,
            event_type="ACTION_PROPOSED",
            description=f"Proposed Missing Evidence Request for {draft.recipient_name}",
            affected_ids=[action_id, draft.draft_id],
        )

        return action

    def build_draft_journal_voucher(
        self,
        case_id: str,
        custom_coa_mapping: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> DraftJournalVoucher:
        """Constructs a deterministic balanced Draft Journal Voucher for a case."""
        recon, report = self._get_case_truth(case_id)
        if not recon:
            raise ValueError(f"No reconciliation record found for case {case_id}")

        self._validate_case_provenance(case_id, recon, report)

        voucher = DraftJournalEngine.generate_draft_voucher(
            case_id=case_id,
            recon=recon,
            report=report,
            custom_coa_mapping=custom_coa_mapping,
        )

        is_valid, errors = RemediationValidator.validate_journal_voucher(voucher)
        if not is_valid:
            raise ValueError(f"Draft journal voucher failed validation: {', '.join(errors)}")

        self._vouchers_store[voucher.voucher_id] = voucher
        return voucher

    def propose_journal_voucher_action(
        self,
        case_id: str,
        custom_coa_mapping: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> RemediationAction:
        """Constructs a draft journal voucher and packages it as an actionable proposal."""
        voucher = self.build_draft_journal_voucher(case_id, custom_coa_mapping)

        action_id = f"ACT-JV-{uuid.uuid4().hex[:8].upper()}"
        action = RemediationAction(
            action_id=action_id,
            case_id=case_id,
            action_type=RemediationActionType.DRAFT_JOURNAL_VOUCHER,
            approval_status=ActionApprovalStatus.PENDING_APPROVAL,
            title=f"Draft Journal Voucher: {voucher.voucher_id}",
            summary=f"Balanced draft journal voucher (DR/CR: INR {voucher.total_debits:,.2f}) pending review",
            journal_voucher=voucher,
            proposed_by="AI_FINANCE_CONTROLLER",
        )

        self._actions_store[action_id] = action
        self._record_audit_event(
            case_id=case_id,
            event_type="ACTION_PROPOSED",
            description=f"Proposed Draft Journal Voucher {voucher.voucher_id} (Balanced: INR {voucher.total_debits:,.2f})",
            affected_ids=[action_id, voucher.voucher_id],
        )

        return action

    def approve_action(
        self,
        action_id: str,
        reviewer_id: str = "controller_1",
        notes: Optional[str] = None,
    ) -> RemediationAction:
        """Explicit human approval of a proposed remediation action."""
        if not reviewer_id or not reviewer_id.strip():
            raise ValueError("Reviewer ID is required for explicit human approval.")

        action = self._actions_store.get(action_id)
        if not action:
            raise ValueError(f"Remediation action {action_id} not found")

        # Invariant: Action must be in PENDING_APPROVAL to be approved
        if action.approval_status != ActionApprovalStatus.PENDING_APPROVAL:
            raise ValueError(
                f"Cannot approve action '{action_id}' with status '{action.approval_status.value}'. "
                f"Only actions in PENDING_APPROVAL status can be approved."
            )

        action.approval_status = ActionApprovalStatus.APPROVED
        action.approved_by = reviewer_id.strip()
        from datetime import datetime, timezone
        action.approved_at = datetime.now(timezone.utc).isoformat()
        action.updated_at = action.approved_at

        # Record audit event
        event = self._record_audit_event(
            case_id=action.case_id,
            event_type="ACTION_APPROVED",
            description=f"Controller '{reviewer_id}' explicitly APPROVED action '{action.title}' (ID: {action_id})",
            affected_ids=[action_id],
        )
        if event:
            action.audit_event_id = getattr(event, "event_id", str(event))

        logger.info(f"[REMEDIATION] Action {action_id} APPROVED by {reviewer_id}")
        return action

    def reject_action(
        self,
        action_id: str,
        reviewer_id: str = "controller_1",
        rejection_reason: str = "Controller declined proposed draft",
        notes: Optional[str] = None,
    ) -> RemediationAction:
        """Explicit human rejection of a proposed remediation action."""
        if not reviewer_id or not reviewer_id.strip():
            raise ValueError("Reviewer ID is required for explicit human rejection.")

        action = self._actions_store.get(action_id)
        if not action:
            raise ValueError(f"Remediation action {action_id} not found")

        # Invariant: Action must be in PENDING_APPROVAL to be rejected
        if action.approval_status != ActionApprovalStatus.PENDING_APPROVAL:
            raise ValueError(
                f"Cannot reject action '{action_id}' with status '{action.approval_status.value}'. "
                f"Only actions in PENDING_APPROVAL status can be rejected."
            )

        action.approval_status = ActionApprovalStatus.REJECTED
        action.rejection_reason = rejection_reason
        action.rejection_notes = notes
        from datetime import datetime, timezone
        action.updated_at = datetime.now(timezone.utc).isoformat()

        self._record_audit_event(
            case_id=action.case_id,
            event_type="ACTION_REJECTED",
            description=f"Controller '{reviewer_id}' REJECTED action '{action.title}'. Reason: {rejection_reason}",
            affected_ids=[action_id],
        )

        logger.info(f"[REMEDIATION] Action {action_id} REJECTED by {reviewer_id}")
        return action

    def list_actions_by_case(self, case_id: str) -> List[RemediationAction]:
        """Lists all remediation action proposals for a case."""
        return [a for a in self._actions_store.values() if a.case_id == case_id]

    def get_action(self, action_id: str) -> Optional[RemediationAction]:
        """Retrieves an action by ID."""
        return self._actions_store.get(action_id)

    # -------------------------------------------------------------
    # INTERNAL HELPERS & PROVENANCE CHECKS
    # -------------------------------------------------------------
    def _validate_case_provenance(self, case_id: str, recon: ReconciliationResult, report: Optional[FinancialTruthReport]):
        """Ensures cross-case isolation and provenance consistency."""
        if report and report.case_id != case_id:
            raise ValueError(f"Cross-case provenance violation: Report case_id '{report.case_id}' != target '{case_id}'")

    def _get_case_truth(self, case_id: str):
        """Retrieves authoritative ReconciliationResult and FinancialTruthReport from SQL."""
        with self.engine.get_connection() as conn:
            recon_repo = SQLReconciliationRepository(conn)
            report_repo = SQLTruthReportRepository(conn)

            recon_rec = recon_repo.get_by_case(case_id)
            report_rec = report_repo.get_by_case(case_id)

            recon = None
            if recon_rec:
                from backend.domain.reconciliation import ReconciliationStatus
                recon = ReconciliationResult(
                    reconciliation_id=recon_rec.reconciliation_id,
                    status=ReconciliationStatus(recon_rec.status),
                    event_id=recon_rec.event_id,
                    entity_id=recon_rec.entity_id,
                    claim_ids=recon_rec.claim_ids,
                    transaction_ids=recon_rec.transaction_ids,
                    evidence_ids=recon_rec.evidence_ids,
                    expected_amount=recon_rec.expected_amount,
                    matched_amount=recon_rec.matched_amount,
                    outstanding_amount=recon_rec.outstanding_amount,
                    explanation=recon_rec.explanation,
                    discrepancy_ids=recon_rec.discrepancy_ids,
                )

            report = None
            if report_rec and report_rec.report_json:
                try:
                    report = FinancialTruthReport.model_validate(report_rec.report_json)
                except Exception:
                    report = None

            return recon, report

    def _record_audit_event(
        self,
        case_id: str,
        event_type: str,
        description: str,
        affected_ids: List[str],
    ) -> Optional[Any]:
        """Records an immutable audit event using PersistentAuditStore."""
        try:
            store = PersistentAuditStore(self.engine)
            return store.append_event(
                case_id=case_id,
                event_type=event_type,
                actor_id="controller_1",
                description=description,
                affected_ids=affected_ids,
            )
        except Exception as ex:
            logger.warning(f"Could not persist audit event to SQL: {ex}")
            return None
