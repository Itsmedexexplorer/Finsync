"""VERITY Unified Storage Service & Transaction Coordinator (Day 16).

Coordinates multi-domain SQL repositories, manages atomic case lifecycle transactions,
preserves deterministic financial truth, enforces zero evidence mutation, and provides
durable recovery across application restarts.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict, List, Optional, Tuple

from backend.case_processing.result import CaseProcessingResult
from backend.controller.models import ControllerDecision
from backend.portfolio.models import CaseAssignment, CasePortfolioItem
from backend.reconciliation.result import ReconciliationResult, ReconciliationStatus
from backend.reporting.models import FinancialTruthReport
from backend.review.models import AuditEventType, ReviewDecision, ReviewRecord, ReviewStatus
from backend.storage.audit_store import PersistentAuditStore
from backend.storage.database import DatabaseConnection, DatabaseEngine, get_database_engine
from backend.storage.models import (
    AuditEventRecord,
    CaseAssignmentRecord,
    CaseRecord,
    ClaimRecord,
    ControllerDecisionRecord,
    DeduplicationGroupRecord,
    DiscrepancyRecord,
    EntityRecord,
    EvidenceRecord,
    EvidenceReviewRecordModel,
    IdempotencyRecord,
    MatchRelationshipRecord,
    PortfolioStateRecord,
    ReconciliationRecordModel,
    ReviewNoteRecord,
    ReviewRecordModel,
    TransactionRecord,
    TruthReportRecord,
)
from backend.storage.repositories.sql.audit import SQLAuditRepository
from backend.storage.repositories.sql.case import SQLCaseRepository
from backend.storage.repositories.sql.claim import SQLClaimRepository
from backend.storage.repositories.sql.controller import SQLControllerRepository
from backend.storage.repositories.sql.deduplication import SQLDeduplicationRepository
from backend.storage.repositories.sql.discrepancy import SQLDiscrepancyRepository
from backend.storage.repositories.sql.entity import SQLEntityRepository
from backend.storage.repositories.sql.evidence import SQLEvidenceRepository
from backend.storage.repositories.sql.idempotency import SQLIdempotencyRepository
from backend.storage.repositories.sql.matching import SQLMatchRepository
from backend.storage.repositories.sql.portfolio import SQLPortfolioRepository
from backend.storage.repositories.sql.reconciliation import SQLReconciliationRepository
from backend.storage.repositories.sql.reporting import SQLTruthReportRepository
from backend.storage.repositories.sql.review import SQLReviewRepository
from backend.storage.repositories.sql.transaction import SQLTransactionRepository

logger = logging.getLogger("verity.storage.service")


def _get_val(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        val = obj.get(key, default)
        return default if val is None else val
    val = getattr(obj, key, default)
    return default if val is None else val


class StorageConflictError(Exception):
    """Raised when an idempotency conflict occurs (same key with different payload)."""
    pass


class StorageService:
    """Unified service for durable persistence, atomic transactions, and audit integrity."""

    def __init__(self, engine: Optional[DatabaseEngine] = None) -> None:
        self.engine = engine or get_database_engine()
        self.audit_store = PersistentAuditStore(self.engine)

    # -------------------------------------------------------------
    # 1. ATOMIC CASE LIFECYCLE PERSISTENCE
    # -------------------------------------------------------------
    def process_and_persist_case(
        self,
        case_result: CaseProcessingResult,
        controller_decision: Optional[ControllerDecision] = None,
        review_record: Optional[ReviewRecord] = None,
        portfolio_item: Optional[CasePortfolioItem] = None,
        raw_evidence_list: Optional[List[Any]] = None,
        raw_claims_list: Optional[List[Any]] = None,
        raw_entities_list: Optional[List[Any]] = None,
        raw_transactions_list: Optional[List[Any]] = None,
        raw_discrepancies_list: Optional[List[Any]] = None,
    ) -> CaseRecord:
        """Atomically persists the complete financial truth pipeline artifacts for a case.
        
        Guarantees: If ANY stage fails, all mutations rollback cleanly (All-or-Nothing).
        """
        cid = case_result.case_id

        with self.engine.transaction() as conn:
            # 1. Core Case Record
            case_repo = SQLCaseRepository(conn)
            case_rec = CaseRecord(
                case_id=cid,
                status=case_result.status,
                confidence_score=case_result.confidence_score,
                total_execution_time_ms=case_result.total_execution_time_ms,
                financial_summary=case_result.financial_summary,
                warnings=case_result.warnings,
                errors=case_result.errors,
                metadata=case_result.metadata,
            )
            case_repo.create(case_rec)

            # 2. Raw Evidence Records (Immutable)
            ev_repo = SQLEvidenceRepository(conn)
            if raw_evidence_list:
                for ev in raw_evidence_list:
                    raw_pay = _get_val(ev, "raw_payload", "") or ""
                    sha_val = _get_val(ev, "sha256_hash", None)
                    if not sha_val or sha_val == "0" * 64:
                        import hashlib
                        sha_val = hashlib.sha256(raw_pay.encode("utf-8")).hexdigest()
                    ev_rec = EvidenceRecord(
                        id=_get_val(ev, "id", str(ev)),
                        case_id=cid,
                        modality=str(_get_val(ev, "modality", "DOCUMENT")),
                        source_name=_get_val(ev, "source_name", None),
                        source_type=_get_val(ev, "source_type", None),
                        sha256_hash=sha_val,
                        summary=_get_val(ev, "summary", "") or "",
                        raw_payload=raw_pay,
                    )
                    ev_repo.create(ev_rec)

            # 3. Claims Records (Immutable)
            claim_repo = SQLClaimRepository(conn)
            if raw_claims_list:
                for clm in raw_claims_list:
                    clm_rec = ClaimRecord(
                        id=_get_val(clm, "id", str(clm)),
                        case_id=cid,
                        evidence_id=_get_val(clm, "evidence_id", "UNKNOWN"),
                        claim_type=str(_get_val(clm, "claim_type", "INVOICE_ISSUED")),
                        claimed_amount=_get_val(clm, "claimed_amount", None),
                        claimed_date=_get_val(clm, "claimed_date", None),
                        counterparty_hint=_get_val(clm, "counterparty_hint", None),
                        reference_id_hint=_get_val(clm, "reference_id_hint", None),
                        confidence=_get_val(clm, "confidence", 1.0),
                        metadata=_get_val(clm, "metadata", {}) or {},
                    )
                    claim_repo.create(clm_rec)

            # 4. Entity Records
            ent_repo = SQLEntityRepository(conn)
            if raw_entities_list:
                for ent in raw_entities_list:
                    ent_rec = EntityRecord(
                        id=_get_val(ent, "id", str(ent)),
                        case_id=cid,
                        canonical_name=_get_val(ent, "canonical_name", "Unknown"),
                        entity_type=_get_val(ent, "entity_type", None),
                        gstin=_get_val(ent, "gstin", None),
                        pan=_get_val(ent, "pan", None),
                        upi_id=_get_val(ent, "upi_id", None),
                        phone=_get_val(ent, "phone", None),
                        aliases=_get_val(ent, "aliases", []) or [],
                        confidence=_get_val(ent, "confidence", 1.0),
                        resolved_via=_get_val(ent, "resolved_via", None),
                        metadata=_get_val(ent, "metadata", {}) or {},
                    )
                    ent_repo.create(ent_rec)

            # 5. Transactions Records (Immutable)
            txn_repo = SQLTransactionRepository(conn)
            if raw_transactions_list:
                for txn in raw_transactions_list:
                    txn_rec = TransactionRecord(
                        id=_get_val(txn, "id", str(txn)),
                        case_id=cid,
                        amount=float(_get_val(txn, "amount", 0.0)),
                        direction=str(_get_val(txn, "direction", "CREDIT")),
                        timestamp=_get_val(txn, "timestamp", None),
                        bank_reference=_get_val(txn, "bank_reference", None),
                        payment_method=_get_val(txn, "payment_method", None),
                        counterparty_entity_id=_get_val(txn, "counterparty_entity_id", None),
                        account_number_mask=_get_val(txn, "account_number_mask", None),
                        metadata=_get_val(txn, "metadata", {}) or {},
                    )
                    txn_repo.create(txn_rec)

            # 6. Discrepancies Records
            disc_repo = SQLDiscrepancyRepository(conn)
            discs_to_save = list(raw_discrepancies_list or [])
            if not discs_to_save and case_result.report and case_result.report.contradiction_summary:
                discs_to_save = case_result.report.contradiction_summary

            for d in discs_to_save:
                d_rec = DiscrepancyRecord(
                    id=_get_val(d, "id", _get_val(d, "discrepancy_id", str(d))),
                    case_id=cid,
                    discrepancy_type=str(_get_val(d, "discrepancy_type", "UNKNOWN")),
                    severity=str(_get_val(d, "severity", "WARNING")),
                    message=_get_val(d, "message", ""),
                    expected_value=_get_val(d, "expected_value", None),
                    observed_value=_get_val(d, "observed_value", None),
                    involved_evidence_ids=list(_get_val(d, "involved_evidence_ids", []) or []),
                    involved_claim_ids=list(_get_val(d, "involved_claim_ids", []) or []),
                    involved_transaction_ids=list(_get_val(d, "involved_transaction_ids", []) or []),
                    metadata=_get_val(d, "metadata", {}) or {},
                )
                disc_repo.create(d_rec)

            # 7. Authoritative Reconciliation Result (Deterministic Truth)
            if case_result.reconciliation:
                recon = case_result.reconciliation
                recon_repo = SQLReconciliationRepository(conn)
                recon_rec = ReconciliationRecordModel(
                    reconciliation_id=recon.reconciliation_id,
                    case_id=cid,
                    status=recon.status.value,
                    event_id=recon.event_id,
                    entity_id=recon.entity_id,
                    claim_ids=list(recon.claim_ids),
                    transaction_ids=list(recon.transaction_ids),
                    evidence_ids=list(recon.evidence_ids),
                    expected_amount=recon.expected_amount,
                    matched_amount=recon.matched_amount,
                    outstanding_amount=recon.outstanding_amount,
                    currency=recon.currency,
                    confidence_score=recon.confidence_score,
                    supporting_signals=list(recon.supporting_signals),
                    contradicting_signals=list(recon.contradicting_signals),
                    discrepancy_ids=list(recon.discrepancy_ids),
                    match_relationship_ids=list(recon.match_relationship_ids),
                    deduplication_group_ids=list(recon.deduplication_group_ids),
                    explanation=recon.explanation,
                    reason_codes=list(recon.reason_codes),
                    provenance=recon.provenance,
                    metadata=recon.metadata,
                )
                recon_repo.create(recon_rec)

            # 8. Truth Report Record
            if case_result.report:
                rep = case_result.report
                rep_repo = SQLTruthReportRepository(conn)
                rep_rec = TruthReportRecord(
                    case_id=cid,
                    title=rep.title,
                    summary=rep.summary,
                    text_report=case_result.to_text_report(),
                    status=rep.status.value,
                    confidence_score=rep.confidence_score,
                    financial_summary=rep.financial_summary.model_dump(mode="json") if rep.financial_summary else {},
                    provenance=rep.provenance.model_dump(mode="json") if rep.provenance else {},
                    requires_human_review=getattr(rep, "requires_human_review", bool(rep.unresolved_items or rep.status.value != "CONFIRMED")),
                    report_json=rep.model_dump(mode="json"),
                )
                rep_repo.create(rep_rec)

            # 9. Controller Decision Record
            if controller_decision:
                ctrl_repo = SQLControllerRepository(conn)
                ctrl_rec = ControllerDecisionRecord(
                    case_id=cid,
                    risk_level=controller_decision.risk_level.value,
                    decision=controller_decision.decision.value,
                    requires_human_review=controller_decision.requires_human_review,
                    confidence=controller_decision.confidence,
                    reasons=list(controller_decision.reasons),
                    recommended_actions=[
                        a.title if hasattr(a, "title") else str(a)
                        for a in controller_decision.recommended_actions
                    ],
                    executive_brief=getattr(controller_decision, "executive_brief", "") or "",
                    metadata=controller_decision.metadata or {},
                )
                ctrl_repo.create(ctrl_rec)

            # 10. Human Review Record
            if review_record:
                rev_repo = SQLReviewRepository(conn)
                closed_ts = None
                if getattr(review_record, "completed_at", None):
                    closed_ts = review_record.completed_at.isoformat() if hasattr(review_record.completed_at, "isoformat") else str(review_record.completed_at)
                elif getattr(review_record, "closed_at", None):
                    closed_ts = review_record.closed_at.isoformat() if hasattr(review_record.closed_at, "isoformat") else str(review_record.closed_at)

                rev_rec = ReviewRecordModel(
                    review_id=review_record.review_id,
                    case_id=cid,
                    status=review_record.status.value,
                    decision=review_record.decision.value if review_record.decision else None,
                    assigned_to=getattr(review_record, "assigned_to", getattr(review_record, "reviewer_id", None)),
                    required_actions=[
                        a.action_id if hasattr(a, "action_id") else str(a)
                        for a in getattr(review_record, "actions", getattr(review_record, "required_actions", []))
                    ],
                    completed_actions=[
                        a.action_id if hasattr(a, "action_id") else str(a)
                        for a in getattr(review_record, "completed_actions", [])
                    ],
                    notes_count=len(getattr(review_record, "notes", [])),
                    inspected_evidence_count=len(getattr(review_record, "reviewed_evidence", getattr(review_record, "inspected_evidence", []))),
                    created_at=review_record.created_at.isoformat() if hasattr(review_record.created_at, "isoformat") else str(review_record.created_at),
                    updated_at=review_record.updated_at.isoformat() if hasattr(review_record.updated_at, "isoformat") else str(review_record.updated_at),
                    closed_at=closed_ts,
                )
                rev_repo.create(rev_rec)

            # 11. Portfolio State Record
            if portfolio_item:
                port_repo = SQLPortfolioRepository(conn)
                port_rec = PortfolioStateRecord(
                    case_id=cid,
                    portfolio_status=portfolio_item.portfolio_status.value,
                    priority=portfolio_item.priority.value,
                    priority_score=getattr(portfolio_item, "priority_score", 0.0),
                    priority_reasons=list(getattr(portfolio_item, "priority_reasons", [])),
                    amount_exposure=portfolio_item.amount_exposure,
                    disputed_amount=portfolio_item.disputed_amount,
                    unresolved_amount=portfolio_item.unresolved_amount,
                    sla_status=portfolio_item.sla_status.value,
                    sla_due_at=portfolio_item.sla_due_at.isoformat() if portfolio_item.sla_due_at else None,
                    sla_elapsed_hours=getattr(portfolio_item, "sla_elapsed_hours", 0.0),
                    sla_remaining_hours=getattr(portfolio_item, "sla_remaining_hours", getattr(portfolio_item, "sla_window_hours", 72.0)),
                    assigned_reviewer_id=portfolio_item.assigned_reviewer_id,
                    assigned_reviewer_name=portfolio_item.assigned_reviewer_name,
                )
                port_repo.save_state(port_rec)

            # 12. Genesis Audit Event
            self.audit_store.append_event(
                case_id=cid,
                event_type=AuditEventType.CASE_PROCESSED if hasattr(AuditEventType, "CASE_PROCESSED") else "CASE_PROCESSED",
                actor_id="system:case_processor",
                description=f"Case {cid} processed and persisted with deterministic status {case_result.status}",
                affected_ids=[cid],
                review_id=review_record.review_id if review_record else None,
                metadata={"confidence": case_result.confidence_score, "status": case_result.status},
                conn=conn,
            )

        logger.info(f"Case {cid} successfully persisted atomically to database.")
        return case_rec

    # -------------------------------------------------------------
    # 2. CASE RETRIEVAL & QUERYING
    # -------------------------------------------------------------
    def get_case_result(self, case_id: str) -> Optional[CaseProcessingResult]:
        """Loads and reconstructs a CaseProcessingResult from persistent storage."""
        with self.engine.get_connection() as conn:
            case_rec = SQLCaseRepository(conn).get(case_id)
            if not case_rec:
                return None

            # Reconstruct Reconciliation
            recon_rec = SQLReconciliationRepository(conn).get_by_case(case_id)
            recon = None
            if recon_rec:
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
                    currency=recon_rec.currency,
                    confidence_score=recon_rec.confidence_score,
                    supporting_signals=recon_rec.supporting_signals,
                    contradicting_signals=recon_rec.contradicting_signals,
                    discrepancy_ids=recon_rec.discrepancy_ids,
                    match_relationship_ids=recon_rec.match_relationship_ids,
                    deduplication_group_ids=recon_rec.deduplication_group_ids,
                    explanation=recon_rec.explanation,
                    reason_codes=recon_rec.reason_codes,
                    provenance=recon_rec.provenance,
                    metadata=recon_rec.metadata,
                )

            # Reconstruct Report
            rep_rec = SQLTruthReportRepository(conn).get_by_case(case_id)
            report = None
            if rep_rec and rep_rec.report_json:
                try:
                    report = FinancialTruthReport.model_validate(rep_rec.report_json)
                except Exception:
                    pass

            return CaseProcessingResult(
                case_id=case_rec.case_id,
                status=case_rec.status,
                confidence_score=case_rec.confidence_score,
                reconciliation=recon,
                report=report,
                financial_summary=case_rec.financial_summary,
                total_execution_time_ms=case_rec.total_execution_time_ms,
                warnings=case_rec.warnings,
                errors=case_rec.errors,
                metadata=case_rec.metadata,
            )

    def list_cases(self, limit: int = 100, offset: int = 0) -> List[CaseRecord]:
        """Lists high-level case records from database."""
        with self.engine.get_connection() as conn:
            return SQLCaseRepository(conn).list_all(limit=limit, offset=offset)

    def delete_case_if_allowed(self, case_id: str) -> bool:
        """Deletes a case record and cascaded entities."""
        with self.engine.transaction() as conn:
            return SQLCaseRepository(conn).delete_if_allowed(case_id)

    # -------------------------------------------------------------
    # 3. HUMAN REVIEW PERSISTENCE
    # -------------------------------------------------------------
    def save_review(self, record: ReviewRecordModel, conn: Optional[DatabaseConnection] = None) -> ReviewRecordModel:
        """Persists or updates a human review record."""
        if conn is not None:
            return SQLReviewRepository(conn).create(record)
        with self.engine.transaction() as tx_conn:
            return SQLReviewRepository(tx_conn).create(record)

    def get_review(self, case_id: str) -> Optional[ReviewRecordModel]:
        """Fetches persistent human review record for a case."""
        with self.engine.get_connection() as conn:
            return SQLReviewRepository(conn).get_by_case(case_id)

    def add_review_note(self, note: ReviewNoteRecord, conn: Optional[DatabaseConnection] = None) -> ReviewNoteRecord:
        """Persists an append-only review note."""
        if conn is not None:
            return SQLReviewRepository(conn).add_note(note)
        with self.engine.transaction() as tx_conn:
            return SQLReviewRepository(tx_conn).add_note(note)

    def list_review_notes(self, case_id: str) -> List[ReviewNoteRecord]:
        """Lists all review notes for a case."""
        with self.engine.get_connection() as conn:
            return SQLReviewRepository(conn).list_notes(case_id)

    def add_evidence_inspection(self, inspection: EvidenceReviewRecordModel, conn: Optional[DatabaseConnection] = None) -> EvidenceReviewRecordModel:
        """Persists an evidence inspection record."""
        if conn is not None:
            return SQLReviewRepository(conn).add_inspection(inspection)
        with self.engine.transaction() as tx_conn:
            return SQLReviewRepository(tx_conn).add_inspection(inspection)

    def list_evidence_inspections(self, case_id: str) -> List[EvidenceReviewRecordModel]:
        """Lists all evidence inspections for a case."""
        with self.engine.get_connection() as conn:
            return SQLReviewRepository(conn).list_inspections(case_id)

    # -------------------------------------------------------------
    # 4. PORTFOLIO & ASSIGNMENT PERSISTENCE
    # -------------------------------------------------------------
    def save_portfolio_state(self, state: PortfolioStateRecord, conn: Optional[DatabaseConnection] = None) -> PortfolioStateRecord:
        """Persists operational portfolio state."""
        if conn is not None:
            return SQLPortfolioRepository(conn).save_state(state)
        with self.engine.transaction() as tx_conn:
            return SQLPortfolioRepository(tx_conn).save_state(state)

    def get_portfolio_state(self, case_id: str) -> Optional[PortfolioStateRecord]:
        """Retrieves operational portfolio state for a case."""
        with self.engine.get_connection() as conn:
            return SQLPortfolioRepository(conn).get_state(case_id)

    def list_portfolio_states(self) -> List[PortfolioStateRecord]:
        """Retrieves all operational portfolio states."""
        with self.engine.get_connection() as conn:
            return SQLPortfolioRepository(conn).list_states()

    def save_assignment(self, assignment: CaseAssignmentRecord, conn: Optional[DatabaseConnection] = None) -> CaseAssignmentRecord:
        """Persists reviewer assignment."""
        if conn is not None:
            return SQLPortfolioRepository(conn).save_assignment(assignment)
        with self.engine.transaction() as tx_conn:
            return SQLPortfolioRepository(tx_conn).save_assignment(assignment)

    def get_assignment(self, case_id: str) -> Optional[CaseAssignmentRecord]:
        """Retrieves active reviewer assignment for a case."""
        with self.engine.get_connection() as conn:
            return SQLPortfolioRepository(conn).get_assignment(case_id)

    def list_assignments(self) -> List[CaseAssignmentRecord]:
        """Retrieves all active reviewer assignments."""
        with self.engine.get_connection() as conn:
            return SQLPortfolioRepository(conn).list_assignments()

    # -------------------------------------------------------------
    # 5. IDEMPOTENCY LOCKING
    # -------------------------------------------------------------
    def check_idempotency(self, key: str, request_hash: str) -> Tuple[bool, Optional[IdempotencyRecord]]:
        """Checks if a request key has already been processed.
        
        Returns:
            (is_duplicate, existing_record)
        Raises:
            StorageConflictError: If key was used with a different request_hash.
        """
        with self.engine.get_connection() as conn:
            repo = SQLIdempotencyRepository(conn)
            existing = repo.get(key)
            if not existing:
                return False, None

            if existing.request_hash != request_hash:
                raise StorageConflictError(
                    f"Idempotency key '{key}' was previously executed with a different request payload."
                )
            return True, existing

    def record_idempotency(
        self,
        key: str,
        case_id: str,
        request_hash: str,
        response_reference: Optional[str] = None,
        conn: Optional[DatabaseConnection] = None,
    ) -> IdempotencyRecord:
        """Records an idempotency lock entry."""
        rec = IdempotencyRecord(
            key=key,
            case_id=case_id,
            request_hash=request_hash,
            response_reference=response_reference,
            status="COMPLETED",
        )
        if conn is not None:
            return SQLIdempotencyRepository(conn).create(rec)
        with self.engine.transaction() as tx_conn:
            return SQLIdempotencyRepository(tx_conn).create(rec)

    # -------------------------------------------------------------
    # 6. STORAGE STATS & HEALTH
    # -------------------------------------------------------------
    def get_storage_stats(self) -> Dict[str, Any]:
        """Returns row counts and metadata across all persistent tables."""
        with self.engine.get_connection() as conn:
            stats = {}
            tables = [
                "cases", "evidence", "claims", "entities", "transactions",
                "match_relationships", "deduplication_groups", "discrepancies",
                "reconciliation_results", "truth_reports", "controller_decisions",
                "reviews", "review_notes", "evidence_inspections",
                "audit_events", "case_assignments", "portfolio_states",
                "idempotency_records",
            ]
            for tbl in tables:
                try:
                    cur = conn.execute(f"SELECT COUNT(*) AS c FROM {tbl};")
                    stats[tbl] = cur.fetchone()["c"]
                except Exception:
                    stats[tbl] = 0
            return stats

    def check_health(self) -> Dict[str, Any]:
        """Performs live connectivity and storage health diagnostics."""
        health = self.engine.check_health()
        if health.get("status") == "HEALTHY":
            stats = self.get_storage_stats()
            health["tables_count"] = len(stats)
            health["total_cases_stored"] = stats.get("cases", 0)
            health["total_audit_events"] = stats.get("audit_events", 0)
        return health


# Global Storage Service Singleton
_GLOBAL_STORAGE_SERVICE: Optional[StorageService] = None
_STORAGE_SERVICE_LOCK = threading.RLock()


def get_storage_service(engine: Optional[DatabaseEngine] = None) -> StorageService:
    """Returns singleton StorageService instance."""
    global _GLOBAL_STORAGE_SERVICE
    with _STORAGE_SERVICE_LOCK:
        if _GLOBAL_STORAGE_SERVICE is None:
            _GLOBAL_STORAGE_SERVICE = StorageService(engine)
        return _GLOBAL_STORAGE_SERVICE


def reset_storage_service() -> None:
    """Resets global storage service (used in test teardown)."""
    global _GLOBAL_STORAGE_SERVICE
    with _STORAGE_SERVICE_LOCK:
        _GLOBAL_STORAGE_SERVICE = None
