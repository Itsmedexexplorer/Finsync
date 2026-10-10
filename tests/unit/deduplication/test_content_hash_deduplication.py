"""Unit tests for Cryptographic Content Deduplication in VERITY."""

import pytest
from backend.deduplication.engine import DeduplicationEngine
from backend.deduplication.result import DeduplicationStatus
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType


@pytest.fixture
def engine() -> DeduplicationEngine:
    return DeduplicationEngine()


def test_cryptographic_content_hash_duplicates_grouped(engine: DeduplicationEngine) -> None:
    """Two evidence items with identical SHA-256 payload hash -> DUPLICATE_EVIDENCE_CONTENT."""
    ev1 = Evidence(
        id="EVID-SS-01",
        modality=EvidenceModality.PAYMENT_SCREENSHOT,
        source_type=EvidenceSourceType.MANUAL_UPLOAD,
        source_name="screenshot.png",
        raw_payload="SCREENSHOT_BYTES_IDENTICAL_12345",
        content_hash="mock_sha256_hash_12345",
    )
    ev2 = Evidence(
        id="EVID-SS-02",
        modality=EvidenceModality.PAYMENT_SCREENSHOT,
        source_type=EvidenceSourceType.MANUAL_UPLOAD,
        source_name="screenshot_copy.png",
        raw_payload="SCREENSHOT_BYTES_IDENTICAL_12345",
        content_hash="mock_sha256_hash_12345",
    )

    result = engine.deduplicate(evidence_items=[ev1, ev2])
    assert len(result.groups) == 1
    grp = result.groups[0]
    assert grp.status == DeduplicationStatus.DUPLICATE_EVIDENCE_CONTENT
    assert set(grp.member_evidence_ids) == {"EVID-SS-01", "EVID-SS-02"}
    assert grp.score == 1.0
    assert "EXACT_CONTENT_HASH" in grp.matched_signals


def test_different_hashes_not_flagged_as_content_duplicates(engine: DeduplicationEngine) -> None:
    """Different files with distinct hashes are not marked as DUPLICATE_EVIDENCE_CONTENT."""
    ev1 = Evidence(
        id="E1",
        modality=EvidenceModality.BANK_STATEMENT,
        source_type=EvidenceSourceType.BANK_CSV,
        source_name="stmt.csv",
        raw_payload="row1",
        content_hash="hash_aaa",
    )
    ev2 = Evidence(
        id="E2",
        modality=EvidenceModality.PAYMENT_SCREENSHOT,
        source_type=EvidenceSourceType.MANUAL_UPLOAD,
        source_name="ss.png",
        raw_payload="image_bytes",
        content_hash="hash_bbb",
    )

    result = engine.deduplicate(evidence_items=[ev1, ev2])
    content_dup_groups = [g for g in result.groups if g.status == DeduplicationStatus.DUPLICATE_EVIDENCE_CONTENT]
    assert len(content_dup_groups) == 0
