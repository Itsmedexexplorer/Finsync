"""Unit tests for API Security Validator."""

import pytest
from fastapi import HTTPException
from backend.api.security import SecurityValidator
from backend.case_processing.models import CaseInput
from backend.config import Settings
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.transaction import Transaction, TransactionDirection


def test_sanitize_filename_path_traversal() -> None:
    unsafe_name = "../../etc/passwd"
    clean = SecurityValidator.sanitize_filename(unsafe_name)
    assert "/" not in clean
    assert ".." not in clean
    assert "passwd" in clean

    win_unsafe = "..\\..\\Windows\\System32\\calc.exe"
    clean_win = SecurityValidator.sanitize_filename(win_unsafe)
    assert "\\" not in clean_win
    assert "calc.exe" in clean_win


def test_sanitize_filename_null_bytes_and_illegal_chars() -> None:
    dirty = "invoice\0_july<2026>:final?.pdf"
    clean = SecurityValidator.sanitize_filename(dirty)
    assert "\0" not in clean
    assert "<" not in clean
    assert ">" not in clean
    assert ":" not in clean
    assert "?" not in clean
    assert clean.endswith(".pdf")


def test_sanitize_filename_empty() -> None:
    clean = SecurityValidator.sanitize_filename("")
    assert clean == "unnamed_evidence.txt"

    clean_spaces = SecurityValidator.sanitize_filename("   ...  ")
    assert clean_spaces == "sanitized_evidence.txt"


def test_validate_file_extension_allowed_and_rejected() -> None:
    assert SecurityValidator.validate_file_extension("bank_statement.csv") == ".csv"
    assert SecurityValidator.validate_file_extension("INVOICE.PDF") == ".pdf"
    assert SecurityValidator.validate_file_extension("screenshot.PNG") == ".png"
    assert SecurityValidator.validate_file_extension("chat.TXT") == ".txt"

    with pytest.raises(HTTPException) as exc_info:
        SecurityValidator.validate_file_extension("malware.exe")
    assert exc_info.value.status_code == 415


def test_validate_content_type_allowed_and_rejected() -> None:
    SecurityValidator.validate_content_type("application/pdf", "doc.pdf")
    SecurityValidator.validate_content_type("text/csv; charset=utf-8", "data.csv")
    SecurityValidator.validate_content_type("image/png", "img.png")

    with pytest.raises(HTTPException) as exc_info:
        SecurityValidator.validate_content_type("application/x-dosexec", "malware.exe")
    assert exc_info.value.status_code == 415


def test_validate_file_size() -> None:
    max_1mb = 1024 * 1024
    SecurityValidator.validate_file_size(500 * 1024, max_1mb, "small.pdf")

    with pytest.raises(HTTPException) as exc_info:
        SecurityValidator.validate_file_size(2 * 1024 * 1024, max_1mb, "large.pdf")
    assert exc_info.value.status_code == 413


def test_validate_text_length() -> None:
    SecurityValidator.validate_text_length("short text", 100)

    with pytest.raises(HTTPException) as exc_info:
        SecurityValidator.validate_text_length("a" * 150, 100)
    assert exc_info.value.status_code == 400


def test_validate_case_bounds() -> None:
    settings = Settings(
        max_files_per_case=2,
        max_evidence_items=2,
        max_transactions_per_case=2,
    )

    valid_case = CaseInput(case_id="VALID-01")
    SecurityValidator.validate_case_bounds(valid_case, settings)

    oversized_txns = CaseInput(
        case_id="OVER-01",
        transactions=[
            Transaction(id=f"T{i}", amount=100.0, direction=TransactionDirection.CREDIT)
            for i in range(5)
        ],
    )
    with pytest.raises(HTTPException) as exc_info:
        SecurityValidator.validate_case_bounds(oversized_txns, settings)
    assert exc_info.value.status_code == 400
