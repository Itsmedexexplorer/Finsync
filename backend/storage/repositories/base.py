"""Abstract Repository Interfaces & Protocols (Day 16).

Defines strict repository contracts across all storage domains.
Immutable financial records (Evidence, Claims, Transactions, Audit) do not expose update methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from backend.storage.database import DatabaseConnection
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


class BaseRepository(ABC):
    """Base repository associated with a database connection."""

    def __init__(self, conn: DatabaseConnection) -> None:
        self.conn = conn


class CaseRepository(BaseRepository):
    """Repository contract for high-level case records."""

    @abstractmethod
    def create(self, record: CaseRecord) -> CaseRecord:
        pass

    @abstractmethod
    def get(self, case_id: str) -> Optional[CaseRecord]:
        pass

    @abstractmethod
    def list_all(self, limit: int = 100, offset: int = 0) -> List[CaseRecord]:
        pass

    @abstractmethod
    def count(self) -> int:
        pass

    @abstractmethod
    def exists(self, case_id: str) -> bool:
        pass

    @abstractmethod
    def delete_if_allowed(self, case_id: str) -> bool:
        pass


class EvidenceRepository(BaseRepository):
    """Repository contract for Evidence records (IMMUTABLE)."""

    @abstractmethod
    def create(self, record: EvidenceRecord) -> EvidenceRecord:
        pass

    @abstractmethod
    def create_batch(self, records: List[EvidenceRecord]) -> List[EvidenceRecord]:
        pass

    @abstractmethod
    def get(self, evidence_id: str, case_id: Optional[str] = None) -> Optional[EvidenceRecord]:
        pass

    @abstractmethod
    def list_by_case(self, case_id: str) -> List[EvidenceRecord]:
        pass

    @abstractmethod
    def count_by_case(self, case_id: str) -> int:
        pass

    @abstractmethod
    def find_by_hash(self, sha256_hash: str) -> List[EvidenceRecord]:
        pass


class ClaimRepository(BaseRepository):
    """Repository contract for Claim records (IMMUTABLE)."""

    @abstractmethod
    def create(self, record: ClaimRecord) -> ClaimRecord:
        pass

    @abstractmethod
    def create_batch(self, records: List[ClaimRecord]) -> List[ClaimRecord]:
        pass

    @abstractmethod
    def get(self, claim_id: str, case_id: Optional[str] = None) -> Optional[ClaimRecord]:
        pass

    @abstractmethod
    def list_by_case(self, case_id: str) -> List[ClaimRecord]:
        pass

    @abstractmethod
    def find_by_reference_hint(self, reference_id_hint: str) -> List[ClaimRecord]:
        pass

    @abstractmethod
    def find_by_counterparty(self, counterparty_hint: str) -> List[ClaimRecord]:
        pass


class EntityRepository(BaseRepository):
    """Repository contract for Entity records."""

    @abstractmethod
    def create(self, record: EntityRecord) -> EntityRecord:
        pass

    @abstractmethod
    def create_batch(self, records: List[EntityRecord]) -> List[EntityRecord]:
        pass

    @abstractmethod
    def get(self, entity_id: str, case_id: Optional[str] = None) -> Optional[EntityRecord]:
        pass

    @abstractmethod
    def list_by_case(self, case_id: str) -> List[EntityRecord]:
        pass

    @abstractmethod
    def find_by_name(self, canonical_name: str) -> List[EntityRecord]:
        pass

    @abstractmethod
    def find_by_identifier(self, identifier: str) -> List[EntityRecord]:
        pass

    @abstractmethod
    def list_distinct_entities(self) -> List[Dict[str, Any]]:
        pass


class TransactionRepository(BaseRepository):
    """Repository contract for Transaction records (IMMUTABLE)."""

    @abstractmethod
    def create(self, record: TransactionRecord) -> TransactionRecord:
        pass

    @abstractmethod
    def create_batch(self, records: List[TransactionRecord]) -> List[TransactionRecord]:
        pass

    @abstractmethod
    def get(self, transaction_id: str, case_id: Optional[str] = None) -> Optional[TransactionRecord]:
        pass

    @abstractmethod
    def list_by_case(self, case_id: str) -> List[TransactionRecord]:
        pass

    @abstractmethod
    def find_by_reference(self, bank_reference: str) -> List[TransactionRecord]:
        pass


class MatchRepository(BaseRepository):
    """Repository contract for Match Relationship records."""

    @abstractmethod
    def create(self, record: MatchRelationshipRecord) -> MatchRelationshipRecord:
        pass

    @abstractmethod
    def create_batch(self, records: List[MatchRelationshipRecord]) -> List[MatchRelationshipRecord]:
        pass

    @abstractmethod
    def list_by_case(self, case_id: str) -> List[MatchRelationshipRecord]:
        pass


class DeduplicationRepository(BaseRepository):
    """Repository contract for Deduplication Group records."""

    @abstractmethod
    def create(self, record: DeduplicationGroupRecord) -> DeduplicationGroupRecord:
        pass

    @abstractmethod
    def create_batch(self, records: List[DeduplicationGroupRecord]) -> List[DeduplicationGroupRecord]:
        pass

    @abstractmethod
    def list_by_case(self, case_id: str) -> List[DeduplicationGroupRecord]:
        pass


class DiscrepancyRepository(BaseRepository):
    """Repository contract for Discrepancy records."""

    @abstractmethod
    def create(self, record: DiscrepancyRecord) -> DiscrepancyRecord:
        pass

    @abstractmethod
    def create_batch(self, records: List[DiscrepancyRecord]) -> List[DiscrepancyRecord]:
        pass

    @abstractmethod
    def list_by_case(self, case_id: str) -> List[DiscrepancyRecord]:
        pass

    @abstractmethod
    def find_by_type(self, discrepancy_type: str) -> List[DiscrepancyRecord]:
        pass

    @abstractmethod
    def list_all(self, limit: int = 500) -> List[DiscrepancyRecord]:
        pass


class ReconciliationRepository(BaseRepository):
    """Repository contract for Reconciliation Result records (Deterministic Truth)."""

    @abstractmethod
    def create(self, record: ReconciliationRecordModel) -> ReconciliationRecordModel:
        pass

    @abstractmethod
    def get_by_case(self, case_id: str) -> Optional[ReconciliationRecordModel]:
        pass

    @abstractmethod
    def list_by_cases(self, case_ids: List[str]) -> List[ReconciliationRecordModel]:
        pass


class TruthReportRepository(BaseRepository):
    """Repository contract for Truth Report records."""

    @abstractmethod
    def create(self, record: TruthReportRecord) -> TruthReportRecord:
        pass

    @abstractmethod
    def get_by_case(self, case_id: str) -> Optional[TruthReportRecord]:
        pass


class ControllerRepository(BaseRepository):
    """Repository contract for Controller Decision records."""

    @abstractmethod
    def create(self, record: ControllerDecisionRecord) -> ControllerDecisionRecord:
        pass

    @abstractmethod
    def get_by_case(self, case_id: str) -> Optional[ControllerDecisionRecord]:
        pass


class ReviewRepository(BaseRepository):
    """Repository contract for Human Review records & workflow actions."""

    @abstractmethod
    def create(self, record: ReviewRecordModel) -> ReviewRecordModel:
        pass

    @abstractmethod
    def update(self, record: ReviewRecordModel) -> ReviewRecordModel:
        pass

    @abstractmethod
    def get_by_case(self, case_id: str) -> Optional[ReviewRecordModel]:
        pass

    @abstractmethod
    def add_note(self, note: ReviewNoteRecord) -> ReviewNoteRecord:
        pass

    @abstractmethod
    def list_notes(self, case_id: str) -> List[ReviewNoteRecord]:
        pass

    @abstractmethod
    def add_inspection(self, inspection: EvidenceReviewRecordModel) -> EvidenceReviewRecordModel:
        pass

    @abstractmethod
    def list_inspections(self, case_id: str) -> List[EvidenceReviewRecordModel]:
        pass


class AuditRepository(BaseRepository):
    """Repository contract for Audit Events (STRICTLY APPEND-ONLY)."""

    @abstractmethod
    def append(self, event: AuditEventRecord) -> AuditEventRecord:
        pass

    @abstractmethod
    def list_by_case(self, case_id: str) -> List[AuditEventRecord]:
        pass

    @abstractmethod
    def get_latest_event(self, case_id: str) -> Optional[AuditEventRecord]:
        pass


class PortfolioRepository(BaseRepository):
    """Repository contract for Case Portfolio state & assignments."""

    @abstractmethod
    def save_state(self, state: PortfolioStateRecord) -> PortfolioStateRecord:
        pass

    @abstractmethod
    def get_state(self, case_id: str) -> Optional[PortfolioStateRecord]:
        pass

    @abstractmethod
    def list_states(self) -> List[PortfolioStateRecord]:
        pass

    @abstractmethod
    def save_assignment(self, assignment: CaseAssignmentRecord) -> CaseAssignmentRecord:
        pass

    @abstractmethod
    def get_assignment(self, case_id: str) -> Optional[CaseAssignmentRecord]:
        pass

    @abstractmethod
    def list_assignments(self) -> List[CaseAssignmentRecord]:
        pass


class IdempotencyRepository(BaseRepository):
    """Repository contract for Idempotency locks."""

    @abstractmethod
    def get(self, key: str) -> Optional[IdempotencyRecord]:
        pass

    @abstractmethod
    def create(self, record: IdempotencyRecord) -> IdempotencyRecord:
        pass
