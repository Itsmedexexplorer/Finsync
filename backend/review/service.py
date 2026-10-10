"""Unified Human Review and Case Investigation Service for VERITY."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.case_processing.result import CaseProcessingResult
from backend.controller.models import ControllerDecision
from backend.review.actions import ReviewActionFactory
from backend.review.audit import AuditTrail
from backend.review.models import (
    AuditEvent,
    AuditEventType,
    EvidenceReviewRecord,
    ReviewAction,
    ReviewActionStatus,
    ReviewActionType,
    ReviewDecision,
    ReviewNote,
    ReviewRecord,
    ReviewStatus,
    ReviewSummaryResponse,
)
from backend.review.policy import ReviewPolicyEngine
from backend.review.workflow import InvalidStateTransitionError, ReviewWorkflow


class CaseReviewNotFoundError(KeyError):
    """Raised when an operation is requested on a non-existent review record."""
    pass


class ReviewClosedError(ValueError):
    """Raised when mutation is attempted on a closed/immutable review record."""
    pass


class InvalidReferenceError(ValueError):
    """Raised when an invalid or cross-case reference ID is provided."""
    pass


class ReviewService:
    """Thread-safe orchestration service managing review lifecycles, action tasks, notes, and audit chains."""

    def __init__(self) -> None:
        self._reviews: Dict[str, ReviewRecord] = {}
        self._audit_chains: Dict[str, List[AuditEvent]] = {}
        self._lock = threading.Lock()

    def export_state(self) -> Dict[str, Any]:
        """Serializable snapshot of all reviews and audit chains."""
        with self._lock:
            return {
                "reviews": {cid: r.model_dump(mode="json") for cid, r in self._reviews.items()},
                "audit_chains": {
                    cid: [e.model_dump(mode="json") for e in chain]
                    for cid, chain in self._audit_chains.items()
                },
            }

    def load_state(self, state: Dict[str, Any]) -> None:
        """Restores a snapshot produced by export_state()."""
        with self._lock:
            self._reviews = {
                cid: ReviewRecord.model_validate(r) for cid, r in state.get("reviews", {}).items()
            }
            self._audit_chains = {
                cid: [AuditEvent.model_validate(e) for e in chain]
                for cid, chain in state.get("audit_chains", {}).items()
            }

    # ---------------------------------------------------------
    # AUDIT LOGGING HELPER
    # ---------------------------------------------------------
    def _append_audit_event_unlocked(
        self,
        case_id: str,
        review_id: str,
        event_type: AuditEventType,
        actor_id: str,
        description: str,
        affected_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Appends a new hash-chained AuditEvent inside the lock."""
        chain = self._audit_chains.setdefault(case_id, [])
        prev_hash = chain[-1].current_state_hash if chain else None

        event = AuditTrail.create_event(
            case_id=case_id,
            review_id=review_id,
            event_type=event_type,
            actor_id=actor_id,
            description=description,
            affected_ids=affected_ids or [],
            previous_hash=prev_hash,
            metadata=metadata or {},
        )
        chain.append(event)
        return event

    # ---------------------------------------------------------
    # LIFECYCLE MANAGEMENT
    # ---------------------------------------------------------
    def create_or_get_review(
        self,
        case_result: CaseProcessingResult,
        controller_decision: Optional[ControllerDecision] = None,
    ) -> ReviewRecord:
        """Initializes or retrieves the ReviewRecord for a financial case."""
        case_id = case_result.case_id
        with self._lock:
            if case_id in self._reviews:
                return self._reviews[case_id]

            # Determine initial review policy
            if controller_decision:
                initial_status, priority, reasons = ReviewPolicyEngine.evaluate_initial_review(controller_decision)
                initial_actions = ReviewActionFactory.from_recommendations(controller_decision.recommended_actions)
                selected_rec_ids = [a.action_id for a in initial_actions]
                disc_ids = list(controller_decision.supporting_discrepancy_ids)
                prov_ids = list(
                    controller_decision.supporting_evidence_ids
                    + controller_decision.supporting_claim_ids
                    + controller_decision.supporting_transaction_ids
                    + controller_decision.supporting_discrepancy_ids
                )
            else:
                initial_status = ReviewStatus.NOT_REQUIRED if case_result.status == "CONFIRMED" else ReviewStatus.PENDING
                priority = "HIGH" if initial_status == ReviewStatus.PENDING else "LOW"
                reasons = [f"Case status is {case_result.status}"]
                initial_actions = []
                selected_rec_ids = []
                disc_ids = []
                prov_ids = []

            rev_id = f"REV-{uuid.uuid4().hex[:8].upper()}"
            review = ReviewRecord(
                review_id=rev_id,
                case_id=case_id,
                status=initial_status,
                decision=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                actions=initial_actions,
                selected_recommendation_ids=selected_rec_ids,
                reviewed_discrepancy_ids=disc_ids,
                unresolved_reasons=reasons,
                provenance_ids=list(set(prov_ids)),
                metadata={"priority": priority},
            )
            self._reviews[case_id] = review

            # Log genesis audit event
            self._append_audit_event_unlocked(
                case_id=case_id,
                review_id=rev_id,
                event_type=AuditEventType.REVIEW_CREATED,
                actor_id="system",
                description=f"Case review created in status '{initial_status.value}' (Priority: {priority}).",
                affected_ids=[rev_id, case_id],
                metadata={"status": initial_status.value, "priority": priority},
            )

            return review

    def get_review(self, case_id: str) -> Optional[ReviewRecord]:
        """Retrieves review record for a given case_id."""
        with self._lock:
            return self._reviews.get(case_id)

    def start_review(
        self,
        case_id: str,
        reviewer_id: str = "controller_1",
        reviewer_name: str = "Finance Controller",
    ) -> ReviewRecord:
        """Transitions case review to IN_PROGRESS state."""
        with self._lock:
            review = self._reviews.get(case_id)
            if not review:
                raise CaseReviewNotFoundError(f"Review for case '{case_id}' not found.")

            ReviewWorkflow.validate_transition(review.status, ReviewStatus.IN_PROGRESS)

            review.status = ReviewStatus.IN_PROGRESS
            review.reviewer_id = reviewer_id
            review.reviewer_name = reviewer_name
            review.started_at = review.started_at or datetime.now(timezone.utc)
            review.updated_at = datetime.now(timezone.utc)

            self._append_audit_event_unlocked(
                case_id=case_id,
                review_id=review.review_id,
                event_type=AuditEventType.REVIEW_STARTED,
                actor_id=reviewer_id,
                description=f"Review started by {reviewer_name} ({reviewer_id}).",
                affected_ids=[review.review_id],
            )
            return review

    # ---------------------------------------------------------
    # NOTES & EVIDENCE AUDITING
    # ---------------------------------------------------------
    def add_note(
        self,
        case_id: str,
        reviewer_id: str,
        reviewer_name: str,
        content: str,
    ) -> ReviewNote:
        """Appends an immutable, timestamped note to the case review."""
        with self._lock:
            review = self._reviews.get(case_id)
            if not review:
                raise CaseReviewNotFoundError(f"Review for case '{case_id}' not found.")

            if not ReviewWorkflow.is_modifiable(review.status):
                raise ReviewClosedError(f"Cannot add note to closed review for case '{case_id}'.")

            note = ReviewNote(
                note_id=f"NOTE-{uuid.uuid4().hex[:8].upper()}",
                reviewer_id=reviewer_id,
                reviewer_name=reviewer_name,
                timestamp=datetime.now(timezone.utc),
                content=content.strip(),
            )
            review.notes.append(note)
            review.updated_at = datetime.now(timezone.utc)

            self._append_audit_event_unlocked(
                case_id=case_id,
                review_id=review.review_id,
                event_type=AuditEventType.NOTE_ADDED,
                actor_id=reviewer_id,
                description=f"Note added by {reviewer_name}: '{content[:60]}...'",
                affected_ids=[note.note_id],
            )
            return note

    def mark_evidence_reviewed(
        self,
        case_id: str,
        evidence_id: str,
        reviewer_id: str = "controller_1",
        reviewer_name: str = "Finance Controller",
        notes: Optional[str] = None,
        valid_evidence_ids: Optional[List[str]] = None,
    ) -> EvidenceReviewRecord:
        """Records that an individual evidence item was inspected, preventing cross-case leaks."""
        with self._lock:
            review = self._reviews.get(case_id)
            if not review:
                raise CaseReviewNotFoundError(f"Review for case '{case_id}' not found.")

            if not ReviewWorkflow.is_modifiable(review.status):
                raise ReviewClosedError(f"Cannot review evidence on closed review for case '{case_id}'.")

            if valid_evidence_ids is not None and evidence_id not in valid_evidence_ids:
                raise InvalidReferenceError(f"Evidence '{evidence_id}' does not belong to case '{case_id}'.")

            rec = EvidenceReviewRecord(
                evidence_id=evidence_id,
                reviewer_id=reviewer_id,
                reviewer_name=reviewer_name,
                reviewed_at=datetime.now(timezone.utc),
                notes=notes,
            )
            review.reviewed_evidence.append(rec)
            if evidence_id not in review.reviewed_evidence_ids:
                review.reviewed_evidence_ids.append(evidence_id)
            review.updated_at = datetime.now(timezone.utc)

            self._append_audit_event_unlocked(
                case_id=case_id,
                review_id=review.review_id,
                event_type=AuditEventType.EVIDENCE_REVIEWED,
                actor_id=reviewer_id,
                description=f"Evidence artifact '{evidence_id}' inspected by {reviewer_name}.",
                affected_ids=[evidence_id],
            )
            return rec

    # ---------------------------------------------------------
    # INVESTIGATION ACTIONS
    # ---------------------------------------------------------
    def create_action(
        self,
        case_id: str,
        action_type: ReviewActionType,
        title: str,
        description: str = "",
        priority: int = 1,
        supporting_ids: Optional[List[str]] = None,
        reviewer_id: Optional[str] = None,
    ) -> ReviewAction:
        """Creates an ad-hoc investigation action task."""
        with self._lock:
            review = self._reviews.get(case_id)
            if not review:
                raise CaseReviewNotFoundError(f"Review for case '{case_id}' not found.")

            if not ReviewWorkflow.is_modifiable(review.status):
                raise ReviewClosedError(f"Cannot add action to closed review for case '{case_id}'.")

            action = ReviewAction(
                action_id=f"ACT-{uuid.uuid4().hex[:8].upper()}",
                action_type=action_type,
                title=title,
                description=description,
                priority=priority,
                status=ReviewActionStatus.PENDING,
                reviewer_id=reviewer_id,
                supporting_ids=supporting_ids or [],
            )
            review.actions.append(action)
            review.updated_at = datetime.now(timezone.utc)

            self._append_audit_event_unlocked(
                case_id=case_id,
                review_id=review.review_id,
                event_type=AuditEventType.ACTION_CREATED,
                actor_id=reviewer_id or "controller",
                description=f"Action created: '{title}' [{action_type.value}].",
                affected_ids=[action.action_id],
            )
            return action

    def complete_action(
        self,
        case_id: str,
        action_id: str,
        reviewer_id: str = "controller_1",
        notes: Optional[str] = None,
    ) -> ReviewAction:
        """Marks an investigation action task as completed."""
        with self._lock:
            review = self._reviews.get(case_id)
            if not review:
                raise CaseReviewNotFoundError(f"Review for case '{case_id}' not found.")

            if not ReviewWorkflow.is_modifiable(review.status):
                raise ReviewClosedError(f"Cannot complete action on closed review for case '{case_id}'.")

            target_act: Optional[ReviewAction] = None
            for act in review.actions:
                if act.action_id == action_id:
                    target_act = act
                    break

            if not target_act:
                raise InvalidReferenceError(f"Action '{action_id}' not found in review for case '{case_id}'.")

            target_act.status = ReviewActionStatus.COMPLETED
            target_act.completed_at = datetime.now(timezone.utc)
            target_act.reviewer_id = reviewer_id
            if notes:
                target_act.notes = notes
            review.updated_at = datetime.now(timezone.utc)

            self._append_audit_event_unlocked(
                case_id=case_id,
                review_id=review.review_id,
                event_type=AuditEventType.ACTION_COMPLETED,
                actor_id=reviewer_id,
                description=f"Action '{target_act.title}' ({action_id}) completed.",
                affected_ids=[action_id],
            )
            return target_act

    # ---------------------------------------------------------
    # DECISIONS, RESOLUTION, ESCALATION & CLOSURE
    # ---------------------------------------------------------
    def record_decision(
        self,
        case_id: str,
        decision: ReviewDecision,
        reviewer_id: str = "controller_1",
        reviewer_name: str = "Finance Controller",
        notes: Optional[str] = None,
    ) -> ReviewRecord:
        """Records human reviewer decision WITHOUT mutating deterministic reconciliation facts."""
        with self._lock:
            review = self._reviews.get(case_id)
            if not review:
                raise CaseReviewNotFoundError(f"Review for case '{case_id}' not found.")

            if not ReviewWorkflow.is_modifiable(review.status):
                raise ReviewClosedError(f"Cannot record decision on closed review for case '{case_id}'.")

            review.decision = decision
            review.reviewer_id = reviewer_id
            review.reviewer_name = reviewer_name
            review.updated_at = datetime.now(timezone.utc)

            # Transition workflow state depending on decision
            if decision == ReviewDecision.ESCALATED:
                ReviewWorkflow.validate_transition(review.status, ReviewStatus.ESCALATED)
                review.status = ReviewStatus.ESCALATED
            elif decision in (ReviewDecision.CONFIRMED, ReviewDecision.REJECTED, ReviewDecision.ACKNOWLEDGED):
                if review.status in (ReviewStatus.PENDING, ReviewStatus.IN_PROGRESS):
                    ReviewWorkflow.validate_transition(review.status, ReviewStatus.RESOLVED)
                    review.status = ReviewStatus.RESOLVED

            if notes:
                note = ReviewNote(
                    note_id=f"NOTE-{uuid.uuid4().hex[:8].upper()}",
                    reviewer_id=reviewer_id,
                    reviewer_name=reviewer_name,
                    timestamp=datetime.now(timezone.utc),
                    content=f"[DECISION: {decision.value}] {notes}",
                )
                review.notes.append(note)

            self._append_audit_event_unlocked(
                case_id=case_id,
                review_id=review.review_id,
                event_type=AuditEventType.DECISION_RECORDED,
                actor_id=reviewer_id,
                description=f"Human review decision recorded: '{decision.value}' by {reviewer_name}.",
                affected_ids=[review.review_id],
                metadata={"decision": decision.value},
            )
            return review

    def escalate(
        self,
        case_id: str,
        reason: str,
        reviewer_id: str = "controller_1",
        reviewer_name: str = "Finance Controller",
    ) -> ReviewRecord:
        """Escalates case to senior controller or compliance team."""
        with self._lock:
            review = self._reviews.get(case_id)
            if not review:
                raise CaseReviewNotFoundError(f"Review for case '{case_id}' not found.")

            ReviewWorkflow.validate_transition(review.status, ReviewStatus.ESCALATED)

            review.status = ReviewStatus.ESCALATED
            review.escalation_reason = reason
            review.reviewer_id = reviewer_id
            review.reviewer_name = reviewer_name
            review.updated_at = datetime.now(timezone.utc)

            self._append_audit_event_unlocked(
                case_id=case_id,
                review_id=review.review_id,
                event_type=AuditEventType.CASE_ESCALATED,
                actor_id=reviewer_id,
                description=f"Case escalated by {reviewer_name}: '{reason}'.",
                affected_ids=[review.review_id],
                metadata={"escalation_reason": reason},
            )
            return review

    def resolve(
        self,
        case_id: str,
        reviewer_id: str = "controller_1",
        reviewer_name: str = "Finance Controller",
        notes: Optional[str] = None,
    ) -> ReviewRecord:
        """Marks review investigation as RESOLVED."""
        with self._lock:
            review = self._reviews.get(case_id)
            if not review:
                raise CaseReviewNotFoundError(f"Review for case '{case_id}' not found.")

            ReviewWorkflow.validate_transition(review.status, ReviewStatus.RESOLVED)

            review.status = ReviewStatus.RESOLVED
            review.reviewer_id = reviewer_id
            review.reviewer_name = reviewer_name
            review.updated_at = datetime.now(timezone.utc)

            if notes:
                review.notes.append(ReviewNote(
                    note_id=f"NOTE-{uuid.uuid4().hex[:8].upper()}",
                    reviewer_id=reviewer_id,
                    reviewer_name=reviewer_name,
                    timestamp=datetime.now(timezone.utc),
                    content=f"[RESOLUTION] {notes}",
                ))

            self._append_audit_event_unlocked(
                case_id=case_id,
                review_id=review.review_id,
                event_type=AuditEventType.REVIEW_RESOLVED,
                actor_id=reviewer_id,
                description=f"Review marked RESOLVED by {reviewer_name}.",
                affected_ids=[review.review_id],
            )
            return review

    def close(
        self,
        case_id: str,
        reviewer_id: str = "controller_1",
        reviewer_name: str = "Finance Controller",
        notes: Optional[str] = None,
    ) -> ReviewRecord:
        """Permanently closes review record, sealing it against further modifications."""
        with self._lock:
            review = self._reviews.get(case_id)
            if not review:
                raise CaseReviewNotFoundError(f"Review for case '{case_id}' not found.")

            ReviewWorkflow.validate_transition(review.status, ReviewStatus.CLOSED)

            review.status = ReviewStatus.CLOSED
            review.completed_at = datetime.now(timezone.utc)
            review.updated_at = datetime.now(timezone.utc)

            if notes:
                review.notes.append(ReviewNote(
                    note_id=f"NOTE-{uuid.uuid4().hex[:8].upper()}",
                    reviewer_id=reviewer_id,
                    reviewer_name=reviewer_name,
                    timestamp=datetime.now(timezone.utc),
                    content=f"[CLOSURE] {notes}",
                ))

            self._append_audit_event_unlocked(
                case_id=case_id,
                review_id=review.review_id,
                event_type=AuditEventType.REVIEW_CLOSED,
                actor_id=reviewer_id,
                description=f"Review CLOSED and sealed by {reviewer_name}.",
                affected_ids=[review.review_id],
            )
            return review

    # ---------------------------------------------------------
    # AUDIT VERIFICATION & SUMMARIES
    # ---------------------------------------------------------
    def get_audit_log(self, case_id: str) -> List[AuditEvent]:
        """Returns chronological list of audit events for a case."""
        with self._lock:
            return list(self._audit_chains.get(case_id, []))

    def validate_audit_chain(self, case_id: str) -> Tuple[bool, str]:
        """Cryptographically verifies that the case audit log has not been tampered with."""
        with self._lock:
            events = self._audit_chains.get(case_id, [])
            return AuditTrail.verify_chain(events)

    def get_summary(
        self,
        case_id: str,
        deterministic_status: str,
        controller_risk_level: str,
        requires_review: bool,
    ) -> ReviewSummaryResponse:
        """Returns executive summary distinguishing deterministic truth from human decisions."""
        with self._lock:
            review = self._reviews.get(case_id)
            if not review:
                raise CaseReviewNotFoundError(f"Review for case '{case_id}' not found.")

            events = self._audit_chains.get(case_id, [])
            completed_actions = sum(1 for a in review.actions if a.status == ReviewActionStatus.COMPLETED)
            pending_actions = sum(1 for a in review.actions if a.status == ReviewActionStatus.PENDING)

            duration = 0.0
            if review.started_at:
                end_time = review.completed_at or datetime.now(timezone.utc)
                duration = max(0.0, (end_time - review.started_at).total_seconds())

            return ReviewSummaryResponse(
                case_id=case_id,
                deterministic_status=deterministic_status,
                controller_risk_level=controller_risk_level,
                review_status=review.status,
                review_decision=review.decision,
                requires_human_review=requires_review,
                reviewer_id=review.reviewer_id,
                reviewer_name=review.reviewer_name,
                duration_seconds=duration,
                audit_event_count=len(events),
                evidence_reviewed_count=len(review.reviewed_evidence_ids),
                total_actions_count=len(review.actions),
                completed_actions_count=completed_actions,
                pending_actions_count=pending_actions,
                unresolved_items=review.unresolved_reasons,
                notes_count=len(review.notes),
            )
