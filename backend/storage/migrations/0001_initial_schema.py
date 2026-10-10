"""Initial database schema migration (0001_initial_schema).

Creates all persistent tables, indexes, constraints, and audit structures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.storage.database import DatabaseConnection

VERSION = "0001_initial_schema"
DESCRIPTION = "Create core case, evidence, claims, transactions, reconciliation, review, audit, and portfolio tables"

SCHEMA_SQL = """
-- Schema Migrations Tracking Table
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(64) PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- 1. Cases Table
CREATE TABLE IF NOT EXISTS cases (
    case_id VARCHAR(128) PRIMARY KEY,
    status VARCHAR(64) NOT NULL,
    confidence_score REAL NOT NULL,
    total_execution_time_ms REAL DEFAULT 0.0,
    financial_summary TEXT, -- JSON
    warnings TEXT,          -- JSON List
    errors TEXT,            -- JSON List
    metadata TEXT,          -- JSON Dict
    created_at VARCHAR(64) DEFAULT CURRENT_TIMESTAMP,
    updated_at VARCHAR(64) DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases(created_at);

-- 2. Evidence Table (Immutable)
CREATE TABLE IF NOT EXISTS evidence (
    id VARCHAR(128) PRIMARY KEY,
    case_id VARCHAR(128) NOT NULL,
    modality VARCHAR(64) NOT NULL,
    source_name VARCHAR(256),
    source_type VARCHAR(128),
    sha256_hash VARCHAR(64) NOT NULL,
    summary TEXT,
    raw_payload TEXT,
    created_at VARCHAR(64) NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_evidence_case_id ON evidence(case_id);
CREATE INDEX IF NOT EXISTS idx_evidence_sha256 ON evidence(sha256_hash);
CREATE UNIQUE INDEX IF NOT EXISTS uq_evidence_case_id_id ON evidence(case_id, id);

-- 3. Claims Table (Immutable)
CREATE TABLE IF NOT EXISTS claims (
    id VARCHAR(128) PRIMARY KEY,
    case_id VARCHAR(128) NOT NULL,
    evidence_id VARCHAR(128) NOT NULL,
    claim_type VARCHAR(64) NOT NULL,
    claimed_amount REAL,
    claimed_date VARCHAR(64),
    counterparty_hint VARCHAR(256),
    reference_id_hint VARCHAR(128),
    confidence REAL DEFAULT 1.0,
    metadata TEXT,
    created_at VARCHAR(64) NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_claims_case_id ON claims(case_id);
CREATE INDEX IF NOT EXISTS idx_claims_evidence_id ON claims(evidence_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_claims_case_id_id ON claims(case_id, id);

-- 4. Entities Table
CREATE TABLE IF NOT EXISTS entities (
    id VARCHAR(128) PRIMARY KEY,
    case_id VARCHAR(128) NOT NULL,
    canonical_name VARCHAR(256) NOT NULL,
    entity_type VARCHAR(64),
    gstin VARCHAR(32),
    pan VARCHAR(32),
    upi_id VARCHAR(128),
    phone VARCHAR(32),
    aliases TEXT, -- JSON List
    confidence REAL DEFAULT 1.0,
    resolved_via VARCHAR(128),
    metadata TEXT,
    created_at VARCHAR(64) NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entities_case_id ON entities(case_id);
CREATE INDEX IF NOT EXISTS idx_entities_canonical_name ON entities(canonical_name);

-- 5. Transactions Table (Immutable)
CREATE TABLE IF NOT EXISTS transactions (
    id VARCHAR(128) PRIMARY KEY,
    case_id VARCHAR(128) NOT NULL,
    amount REAL NOT NULL,
    direction VARCHAR(32) NOT NULL,
    timestamp VARCHAR(64),
    bank_reference VARCHAR(128),
    payment_method VARCHAR(64),
    counterparty_entity_id VARCHAR(128),
    account_number_mask VARCHAR(64),
    metadata TEXT,
    created_at VARCHAR(64) NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transactions_case_id ON transactions(case_id);
CREATE INDEX IF NOT EXISTS idx_transactions_bank_ref ON transactions(bank_reference);
CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_case_id_id ON transactions(case_id, id);

-- 6. Match Relationships Table
CREATE TABLE IF NOT EXISTS match_relationships (
    id VARCHAR(128) PRIMARY KEY,
    case_id VARCHAR(128) NOT NULL,
    relationship_type VARCHAR(64) NOT NULL,
    status VARCHAR(64) NOT NULL,
    source_claim_ids TEXT,     -- JSON List
    target_transaction_ids TEXT, -- JSON List
    matched_amount REAL DEFAULT 0.0,
    target_amount REAL DEFAULT 0.0,
    score REAL DEFAULT 1.0,
    matched_signals TEXT,      -- JSON List
    conflicting_signals TEXT,  -- JSON List
    explanation TEXT,
    created_at VARCHAR(64) NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_match_relationships_case_id ON match_relationships(case_id);

-- 7. Deduplication Groups Table
CREATE TABLE IF NOT EXISTS deduplication_groups (
    id VARCHAR(128) PRIMARY KEY,
    case_id VARCHAR(128) NOT NULL,
    group_type VARCHAR(64) NOT NULL,
    member_evidence_ids TEXT, -- JSON List
    member_claim_ids TEXT,    -- JSON List
    canonical_event_id VARCHAR(128),
    confidence REAL DEFAULT 1.0,
    reason TEXT,
    created_at VARCHAR(64) NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dedup_groups_case_id ON deduplication_groups(case_id);

-- 8. Discrepancies Table
CREATE TABLE IF NOT EXISTS discrepancies (
    id VARCHAR(128) PRIMARY KEY,
    case_id VARCHAR(128) NOT NULL,
    discrepancy_type VARCHAR(64) NOT NULL,
    severity VARCHAR(32) NOT NULL,
    message TEXT NOT NULL,
    expected_value TEXT,
    observed_value TEXT,
    involved_evidence_ids TEXT,    -- JSON List
    involved_claim_ids TEXT,       -- JSON List
    involved_transaction_ids TEXT,  -- JSON List
    metadata TEXT,
    created_at VARCHAR(64) NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_discrepancies_case_id ON discrepancies(case_id);
CREATE INDEX IF NOT EXISTS idx_discrepancies_severity ON discrepancies(severity);

-- 9. Reconciliation Results Table (Authoritative Deterministic Truth)
CREATE TABLE IF NOT EXISTS reconciliation_results (
    reconciliation_id VARCHAR(128) PRIMARY KEY,
    case_id VARCHAR(128) NOT NULL UNIQUE,
    status VARCHAR(64) NOT NULL,
    event_id VARCHAR(128),
    entity_id VARCHAR(128),
    claim_ids TEXT,               -- JSON List
    transaction_ids TEXT,         -- JSON List
    evidence_ids TEXT,            -- JSON List
    expected_amount REAL,
    matched_amount REAL DEFAULT 0.0,
    outstanding_amount REAL DEFAULT 0.0,
    currency VARCHAR(16) DEFAULT 'INR',
    confidence_score REAL DEFAULT 1.0,
    supporting_signals TEXT,      -- JSON List
    contradicting_signals TEXT,  -- JSON List
    discrepancy_ids TEXT,         -- JSON List
    match_relationship_ids TEXT,  -- JSON List
    deduplication_group_ids TEXT, -- JSON List
    explanation TEXT NOT NULL,
    reason_codes TEXT,            -- JSON List
    provenance TEXT,              -- JSON Dict
    metadata TEXT,                -- JSON Dict
    created_at VARCHAR(64) NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_reconciliation_case_id ON reconciliation_results(case_id);
CREATE INDEX IF NOT EXISTS idx_reconciliation_status ON reconciliation_results(status);

-- 10. Truth Reports Table
CREATE TABLE IF NOT EXISTS truth_reports (
    case_id VARCHAR(128) PRIMARY KEY,
    title VARCHAR(256) DEFAULT '',
    summary TEXT DEFAULT '',
    text_report TEXT DEFAULT '',
    status VARCHAR(64) NOT NULL,
    confidence_score REAL DEFAULT 1.0,
    financial_summary TEXT,       -- JSON Dict
    provenance TEXT,              -- JSON Dict
    requires_human_review BOOLEAN DEFAULT 0,
    report_json TEXT,             -- JSON Dict
    created_at VARCHAR(64) NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

-- 11. Controller Decisions Table
CREATE TABLE IF NOT EXISTS controller_decisions (
    case_id VARCHAR(128) PRIMARY KEY,
    risk_level VARCHAR(32) NOT NULL,
    decision VARCHAR(64) NOT NULL,
    requires_human_review BOOLEAN DEFAULT 0,
    confidence REAL DEFAULT 1.0,
    reasons TEXT,                 -- JSON List
    recommended_actions TEXT,     -- JSON List
    executive_brief TEXT DEFAULT '',
    metadata TEXT,                -- JSON Dict
    created_at VARCHAR(64) NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_controller_risk ON controller_decisions(risk_level);

-- 12. Human Review Records Table
CREATE TABLE IF NOT EXISTS reviews (
    review_id VARCHAR(128) PRIMARY KEY,
    case_id VARCHAR(128) NOT NULL UNIQUE,
    status VARCHAR(64) DEFAULT 'PENDING',
    decision VARCHAR(64) DEFAULT 'UNRESOLVED',
    assigned_to VARCHAR(128),
    required_actions TEXT,        -- JSON List
    completed_actions TEXT,       -- JSON List
    notes_count INTEGER DEFAULT 0,
    inspected_evidence_count INTEGER DEFAULT 0,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    closed_at VARCHAR(64),
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_reviews_case_id ON reviews(case_id);
CREATE INDEX IF NOT EXISTS idx_reviews_status ON reviews(status);
CREATE INDEX IF NOT EXISTS idx_reviews_decision ON reviews(decision);

-- 13. Review Notes Table (Append-Only)
CREATE TABLE IF NOT EXISTS review_notes (
    note_id VARCHAR(128) PRIMARY KEY,
    case_id VARCHAR(128) NOT NULL,
    review_id VARCHAR(128) NOT NULL,
    author_id VARCHAR(128) NOT NULL,
    author_name VARCHAR(256) NOT NULL,
    note_type VARCHAR(64) DEFAULT 'OBSERVATION',
    content TEXT NOT NULL,
    timestamp VARCHAR(64) NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY (review_id) REFERENCES reviews(review_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_review_notes_case_id ON review_notes(case_id);
CREATE INDEX IF NOT EXISTS idx_review_notes_review_id ON review_notes(review_id);

-- 14. Evidence Review / Inspections Table (Append-Only)
CREATE TABLE IF NOT EXISTS evidence_inspections (
    inspection_id VARCHAR(128) PRIMARY KEY,
    case_id VARCHAR(128) NOT NULL,
    review_id VARCHAR(128) NOT NULL,
    evidence_id VARCHAR(128) NOT NULL,
    reviewer_id VARCHAR(128) NOT NULL,
    verified BOOLEAN DEFAULT 1,
    notes TEXT,
    timestamp VARCHAR(64) NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY (review_id) REFERENCES reviews(review_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_inspections_case_id ON evidence_inspections(case_id);
CREATE INDEX IF NOT EXISTS idx_inspections_evidence_id ON evidence_inspections(evidence_id);

-- 15. Audit Events Table (Strictly Append-Only & Hash-Chained)
CREATE TABLE IF NOT EXISTS audit_events (
    event_id VARCHAR(128) PRIMARY KEY,
    case_id VARCHAR(128) NOT NULL,
    review_id VARCHAR(128),
    event_type VARCHAR(64) NOT NULL,
    actor_id VARCHAR(128) NOT NULL,
    timestamp VARCHAR(64) NOT NULL,
    description TEXT NOT NULL,
    affected_ids TEXT,            -- JSON List
    previous_state_hash VARCHAR(64) NOT NULL,
    current_state_hash VARCHAR(64) NOT NULL,
    sequence_number INTEGER DEFAULT 1,
    metadata TEXT,                -- JSON Dict
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_audit_case_id ON audit_events(case_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_hash ON audit_events(current_state_hash);
CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_case_seq ON audit_events(case_id, sequence_number);

-- 16. Case Assignments Table
CREATE TABLE IF NOT EXISTS case_assignments (
    case_id VARCHAR(128) PRIMARY KEY,
    reviewer_id VARCHAR(128) NOT NULL,
    reviewer_name VARCHAR(256) NOT NULL,
    assigned_at VARCHAR(64) NOT NULL,
    unassigned_at VARCHAR(64),
    active BOOLEAN DEFAULT 1,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_assignments_reviewer_id ON case_assignments(reviewer_id);

-- 17. Portfolio States Table (Operational Layer)
CREATE TABLE IF NOT EXISTS portfolio_states (
    case_id VARCHAR(128) PRIMARY KEY,
    portfolio_status VARCHAR(64) DEFAULT 'NEW',
    priority VARCHAR(32) DEFAULT 'LOW',
    priority_score REAL DEFAULT 0.0,
    priority_reasons TEXT,        -- JSON List
    amount_exposure REAL DEFAULT 0.0,
    disputed_amount REAL DEFAULT 0.0,
    unresolved_amount REAL DEFAULT 0.0,
    sla_status VARCHAR(32) DEFAULT 'ON_TRACK',
    sla_due_at VARCHAR(64),
    sla_elapsed_hours REAL DEFAULT 0.0,
    sla_remaining_hours REAL DEFAULT 0.0,
    assigned_reviewer_id VARCHAR(128),
    assigned_reviewer_name VARCHAR(256),
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_portfolio_status ON portfolio_states(portfolio_status);
CREATE INDEX IF NOT EXISTS idx_portfolio_priority ON portfolio_states(priority);
CREATE INDEX IF NOT EXISTS idx_portfolio_sla ON portfolio_states(sla_status);
CREATE INDEX IF NOT EXISTS idx_portfolio_assigned_rev ON portfolio_states(assigned_reviewer_id);

-- 18. Idempotency Records Table
CREATE TABLE IF NOT EXISTS idempotency_records (
    key VARCHAR(256) PRIMARY KEY,
    case_id VARCHAR(128) NOT NULL,
    request_hash VARCHAR(64) NOT NULL,
    response_reference TEXT,
    status VARCHAR(32) DEFAULT 'COMPLETED',
    created_at VARCHAR(64) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_idempotency_case_id ON idempotency_records(case_id);
CREATE INDEX IF NOT EXISTS idx_idempotency_hash ON idempotency_records(request_hash);
"""


def apply_migration(conn: DatabaseConnection) -> None:
    """Executes initial schema creation statements."""
    conn.raw.executescript(SCHEMA_SQL)
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, description) VALUES (?, ?);",
        (VERSION, DESCRIPTION),
    )
    conn.commit()
