"""Abstract Repository Interfaces & Protocols.

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
        """Keeps the open database connection every repository reads and writes through."""
        self.conn = conn


class CaseRepository(BaseRepository):
    """Repository contract for high-level case records."""

    @abstractmethod
    def create(self, record: CaseRecord) -> CaseRecord:
        """Saves one check."""
        pass

    @abstractmethod
    def get(self, case_id: str) -> Optional[CaseRecord]:
        """Loads one check by its id; None when not found."""
        pass

    @abstractmethod
    def list_all(self, limit: int = 100, offset: int = 0) -> List[CaseRecord]:
        """All check records, newest first, a page at a time."""
        pass

    @abstractmethod
    def count(self) -> int:
        """How many check records are stored."""
        pass

    @abstractmethod
    def exists(self, case_id: str) -> bool:
        """True when a check with this id is stored."""
        pass

    @abstractmethod
    def delete_if_allowed(self, case_id: str) -> bool:
        """Deletes a check and everything stored under it."""
        pass


class EvidenceRepository(BaseRepository):
    """Repository contract for Evidence records (IMMUTABLE)."""

    @abstractmethod
    def create(self, record: EvidenceRecord) -> EvidenceRecord:
        """Saves one evidence item (one uploaded file or statement row)."""
        pass

    @abstractmethod
    def create_batch(self, records: List[EvidenceRecord]) -> List[EvidenceRecord]:
        """Saves many evidence item (one uploaded file or statement row) records in one go."""
        pass

    @abstractmethod
    def get(self, evidence_id: str, case_id: Optional[str] = None) -> Optional[EvidenceRecord]:
        """Loads one evidence item (one uploaded file or statement row) by its id; None when not found."""
        pass

    @abstractmethod
    def list_by_case(self, case_id: str) -> List[EvidenceRecord]:
        """Every evidence item (one uploaded file or statement row) that belongs to one check."""
        pass

    @abstractmethod
    def count_by_case(self, case_id: str) -> int:
        """How many evidence item (one uploaded file or statement row) records one check has."""
        pass

    @abstractmethod
    def find_by_hash(self, sha256_hash: str) -> List[EvidenceRecord]:
        """Earlier evidence item (one uploaded file or statement row) records with the same SHA-256 fingerprint (the same file uploaded again)."""
        pass


class ClaimRepository(BaseRepository):
    """Repository contract for Claim records (IMMUTABLE)."""

    @abstractmethod
    def create(self, record: ClaimRecord) -> ClaimRecord:
        """Saves one claim (what a file says was paid)."""
        pass

    @abstractmethod
    def create_batch(self, records: List[ClaimRecord]) -> List[ClaimRecord]:
        """Saves many claim (what a file says was paid) records in one go."""
        pass

    @abstractmethod
    def get(self, claim_id: str, case_id: Optional[str] = None) -> Optional[ClaimRecord]:
        """Loads one claim (what a file says was paid) by its id; None when not found."""
        pass

    @abstractmethod
    def list_by_case(self, case_id: str) -> List[ClaimRecord]:
        """Every claim (what a file says was paid) that belongs to one check."""
        pass

    @abstractmethod
    def find_by_reference_hint(self, reference_id_hint: str) -> List[ClaimRecord]:
        """Claim (what a file says was paid) records with this payment reference."""
        pass

    @abstractmethod
    def find_by_counterparty(self, counterparty_hint: str) -> List[ClaimRecord]:
        """Claim (what a file says was paid) records naming this person or business."""
        pass


class EntityRepository(BaseRepository):
    """Repository contract for Entity records."""

    @abstractmethod
    def create(self, record: EntityRecord) -> EntityRecord:
        """Saves one person or business."""
        pass

    @abstractmethod
    def create_batch(self, records: List[EntityRecord]) -> List[EntityRecord]:
        """Saves many person or business records in one go."""
        pass

    @abstractmethod
    def get(self, entity_id: str, case_id: Optional[str] = None) -> Optional[EntityRecord]:
        """Loads one person or business by its id; None when not found."""
        pass

    @abstractmethod
    def list_by_case(self, case_id: str) -> List[EntityRecord]:
        """Every person or business that belongs to one check."""
        pass

    @abstractmethod
    def find_by_name(self, canonical_name: str) -> List[EntityRecord]:
        """Person or business records with this name."""
        pass

    @abstractmethod
    def find_by_identifier(self, identifier: str) -> List[EntityRecord]:
        """Person or business records with this GSTIN, PAN, UPI id or phone number."""
        pass

    @abstractmethod
    def list_distinct_entities(self) -> List[Dict[str, Any]]:
        """Every distinct person or business seen across all checks."""
        pass


class TransactionRepository(BaseRepository):
    """Repository contract for Transaction records (IMMUTABLE)."""

    @abstractmethod
    def create(self, record: TransactionRecord) -> TransactionRecord:
        """Saves one bank transaction."""
        pass

    @abstractmethod
    def create_batch(self, records: List[TransactionRecord]) -> List[TransactionRecord]:
        """Saves many bank transaction records in one go."""
        pass

    @abstractmethod
    def get(self, transaction_id: str, case_id: Optional[str] = None) -> Optional[TransactionRecord]:
        """Loads one bank transaction by its id; None when not found."""
        pass

    @abstractmethod
    def list_by_case(self, case_id: str) -> List[TransactionRecord]:
        """Every bank transaction that belongs to one check."""
        pass

    @abstractmethod
    def find_by_reference(self, bank_reference: str) -> List[TransactionRecord]:
        """Bank transaction records with this bank reference (UTR)."""
        pass


class MatchRepository(BaseRepository):
    """Repository contract for Match Relationship records."""

    @abstractmethod
    def create(self, record: MatchRelationshipRecord) -> MatchRelationshipRecord:
        """Saves one match between claims and bank lines."""
        pass

    @abstractmethod
    def create_batch(self, records: List[MatchRelationshipRecord]) -> List[MatchRelationshipRecord]:
        """Saves many match between claims and bank lines records in one go."""
        pass

    @abstractmethod
    def list_by_case(self, case_id: str) -> List[MatchRelationshipRecord]:
        """Every match between claims and bank lines that belongs to one check."""
        pass


class DeduplicationRepository(BaseRepository):
    """Repository contract for Deduplication Group records."""

    @abstractmethod
    def create(self, record: DeduplicationGroupRecord) -> DeduplicationGroupRecord:
        """Saves one duplicate group."""
        pass

    @abstractmethod
    def create_batch(self, records: List[DeduplicationGroupRecord]) -> List[DeduplicationGroupRecord]:
        """Saves many duplicate group records in one go."""
        pass

    @abstractmethod
    def list_by_case(self, case_id: str) -> List[DeduplicationGroupRecord]:
        """Every duplicate group that belongs to one check."""
        pass


class DiscrepancyRepository(BaseRepository):
    """Repository contract for Discrepancy records."""

    @abstractmethod
    def create(self, record: DiscrepancyRecord) -> DiscrepancyRecord:
        """Saves one discrepancy (something that did not add up)."""
        pass

    @abstractmethod
    def create_batch(self, records: List[DiscrepancyRecord]) -> List[DiscrepancyRecord]:
        """Saves many discrepancy (something that did not add up) records in one go."""
        pass

    @abstractmethod
    def list_by_case(self, case_id: str) -> List[DiscrepancyRecord]:
        """Every discrepancy (something that did not add up) that belongs to one check."""
        pass

    @abstractmethod
    def find_by_type(self, discrepancy_type: str) -> List[DiscrepancyRecord]:
        """Discrepancy (something that did not add up) records of one type."""
        pass

    @abstractmethod
    def list_all(self, limit: int = 500) -> List[DiscrepancyRecord]:
        """All discrepancy (something that did not add up) records, newest first, a page at a time."""
        pass


class ReconciliationRepository(BaseRepository):
    """Repository contract for Reconciliation Result records (Deterministic Truth)."""

    @abstractmethod
    def create(self, record: ReconciliationRecordModel) -> ReconciliationRecordModel:
        """Saves one check result."""
        pass

    @abstractmethod
    def get_by_case(self, case_id: str) -> Optional[ReconciliationRecordModel]:
        """The result saved for one check."""
        pass

    @abstractmethod
    def list_by_cases(self, case_ids: List[str]) -> List[ReconciliationRecordModel]:
        """The check results of several checks."""
        pass


class TruthReportRepository(BaseRepository):
    """Repository contract for Truth Report records."""

    @abstractmethod
    def create(self, record: TruthReportRecord) -> TruthReportRecord:
        """Saves one report."""
        pass

    @abstractmethod
    def get_by_case(self, case_id: str) -> Optional[TruthReportRecord]:
        """The report saved for one check."""
        pass


class ControllerRepository(BaseRepository):
    """Repository contract for Controller Decision records."""

    @abstractmethod
    def create(self, record: ControllerDecisionRecord) -> ControllerDecisionRecord:
        """Saves one controller decision."""
        pass

    @abstractmethod
    def get_by_case(self, case_id: str) -> Optional[ControllerDecisionRecord]:
        """The controller decision saved for one check."""
        pass


class ReviewRepository(BaseRepository):
    """Repository contract for Human Review records & workflow actions."""

    @abstractmethod
    def create(self, record: ReviewRecordModel) -> ReviewRecordModel:
        """Saves one review (the user's answer)."""
        pass

    @abstractmethod
    def update(self, record: ReviewRecordModel) -> ReviewRecordModel:
        """Saves changes to an existing review (the user's answer)."""
        pass

    @abstractmethod
    def get_by_case(self, case_id: str) -> Optional[ReviewRecordModel]:
        """The review (the user's answer) saved for one check."""
        pass

    @abstractmethod
    def add_note(self, note: ReviewNoteRecord) -> ReviewNoteRecord:
        """Saves a note the user wrote on a check."""
        pass

    @abstractmethod
    def list_notes(self, case_id: str) -> List[ReviewNoteRecord]:
        """Every note on one check, oldest first."""
        pass

    @abstractmethod
    def add_inspection(self, inspection: EvidenceReviewRecordModel) -> EvidenceReviewRecordModel:
        """Records that the user looked at one piece of evidence."""
        pass

    @abstractmethod
    def list_inspections(self, case_id: str) -> List[EvidenceReviewRecordModel]:
        """Every evidence inspection recorded for one check."""
        pass


class AuditRepository(BaseRepository):
    """Repository contract for Audit Events (STRICTLY APPEND-ONLY)."""

    @abstractmethod
    def append(self, event: AuditEventRecord) -> AuditEventRecord:
        """Adds one event to the end of a check's audit trail."""
        pass

    @abstractmethod
    def list_by_case(self, case_id: str) -> List[AuditEventRecord]:
        """Every audit-trail event that belongs to one check."""
        pass

    @abstractmethod
    def get_latest_event(self, case_id: str) -> Optional[AuditEventRecord]:
        """The newest audit-trail event of a check (its hash starts the next link)."""
        pass


class PortfolioRepository(BaseRepository):
    """Repository contract for Case Portfolio state & assignments."""

    @abstractmethod
    def save_state(self, state: PortfolioStateRecord) -> PortfolioStateRecord:
        """Saves a check's portfolio entry (priority, status, owner)."""
        pass

    @abstractmethod
    def get_state(self, case_id: str) -> Optional[PortfolioStateRecord]:
        """The portfolio entry of one check."""
        pass

    @abstractmethod
    def list_states(self) -> List[PortfolioStateRecord]:
        """Every portfolio entry."""
        pass

    @abstractmethod
    def save_assignment(self, assignment: CaseAssignmentRecord) -> CaseAssignmentRecord:
        """Saves who a check is assigned to."""
        pass

    @abstractmethod
    def get_assignment(self, case_id: str) -> Optional[CaseAssignmentRecord]:
        """Who one check is assigned to."""
        pass

    @abstractmethod
    def list_assignments(self) -> List[CaseAssignmentRecord]:
        """Every assignment."""
        pass


class IdempotencyRepository(BaseRepository):
    """Repository contract for Idempotency locks."""

    @abstractmethod
    def get(self, key: str) -> Optional[IdempotencyRecord]:
        """The stored response for this idempotency key, if the same request was seen before."""
        pass

    @abstractmethod
    def create(self, record: IdempotencyRecord) -> IdempotencyRecord:
        """Remembers the response for an idempotency key."""
        pass
