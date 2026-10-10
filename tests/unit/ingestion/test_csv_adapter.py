"""Unit tests for BankCSVAdapter in VERITY Ingestion subsystem."""

from pathlib import Path
import pytest

from backend.domain.evidence import EvidenceModality, EvidenceSourceType
from backend.ingestion.csv_adapter import BankCSVAdapter
from backend.ingestion.result import IngestionStatus


@pytest.fixture
def csv_adapter() -> BankCSVAdapter:
    return BankCSVAdapter()


def test_csv_adapter_valid_standard_columns(csv_adapter: BankCSVAdapter, tmp_path: Path) -> None:
    csv_text = """Date,Narration,Amount,Reference
15/08/2026,UPI/408219381920/PAYTO/ROHIT,35000.00,408219381920
16/08/2026,NEFT/POOJA/ICICI,125000.00,NEFT12345
"""
    file_path = tmp_path / "statement.csv"
    file_path.write_text(csv_text, encoding="utf-8")

    result = csv_adapter.ingest_file(file_path)
    assert result.status == IngestionStatus.SUCCESS
    assert len(result.evidence_items) == 2
    assert len(result.errors) == 0

    ev1 = result.evidence_items[0]
    assert ev1.modality == EvidenceModality.BANK_STATEMENT
    assert ev1.source_type == EvidenceSourceType.BANK_CSV
    assert "35000.00" in ev1.raw_payload
    assert ev1.metadata["row_index"] == 2
    assert ev1.metadata["normalized_fields"]["date"] == "15/08/2026"
    assert ev1.metadata["normalized_fields"]["amount"] == "35000.00"
    assert len(ev1.content_hash) == 64


def test_csv_adapter_flexible_column_synonyms(csv_adapter: BankCSVAdapter) -> None:
    # Testing alternative Indian banking headers: Value Date, Particulars, Deposit, UTR
    csv_payload = """Value Date,Particulars,Deposit,UTR
10/08/2026,UPI-SETTLE-RAZORPAY,45000.00,RRN408219001
"""
    result = csv_adapter.ingest_payload(csv_payload, source_name="hdfc_export.csv")
    assert result.status == IngestionStatus.SUCCESS
    assert len(result.evidence_items) == 1

    ev = result.evidence_items[0]
    assert ev.metadata["normalized_fields"]["date"] == "10/08/2026"
    assert ev.metadata["normalized_fields"]["narration"] == "UPI-SETTLE-RAZORPAY"
    assert ev.metadata["normalized_fields"]["credit"] == "45000.00"
    assert ev.metadata["normalized_fields"]["reference"] == "RRN408219001"


def test_csv_adapter_malformed_rows_partial_success(csv_adapter: BankCSVAdapter) -> None:
    csv_payload = """Date,Narration,Amount,Ref
15/08/2026,Valid Row 1,10000.00,REF1
16/08/2026,Bad Row Extra Col,20000.00,REF2,UNEXPECTED_COL
17/08/2026,Valid Row 3,30000.00,REF3
"""
    result = csv_adapter.ingest_payload(csv_payload, source_name="partial.csv")
    assert result.status == IngestionStatus.PARTIAL_SUCCESS
    assert len(result.evidence_items) == 2
    assert len(result.errors) == 1

    err = result.errors[0]
    assert err.row_index == 3
    assert "mismatch" in err.message.lower()
    assert "Bad Row Extra Col" in err.raw_data


def test_csv_adapter_unrecognizable_header(csv_adapter: BankCSVAdapter) -> None:
    csv_payload = """ColA,ColB,ColC
Val1,Val2,Val3
"""
    result = csv_adapter.ingest_payload(csv_payload, source_name="unrecognized.csv")
    assert result.status == IngestionStatus.MALFORMED_DATA
    assert len(result.evidence_items) == 0
    assert len(result.errors) == 1
    assert "lacks recognizable banking columns" in result.errors[0].message


def test_csv_adapter_empty_and_whitespace(csv_adapter: BankCSVAdapter) -> None:
    # Empty payload
    res_empty = csv_adapter.ingest_payload("", source_name="empty.csv")
    assert res_empty.status == IngestionStatus.INVALID_INPUT

    # Header only
    res_header_only = csv_adapter.ingest_payload("Date,Narration,Amount\n", source_name="header_only.csv")
    assert res_header_only.status == IngestionStatus.INVALID_INPUT

    # Whitespace in headers and data
    res_ws = csv_adapter.ingest_payload(
        "  Date  ,  Narration  ,  Amount  \n  15/08/2026  ,  UPI Payment  ,  500.00  ",
        source_name="ws.csv",
    )
    assert res_ws.status == IngestionStatus.SUCCESS
    assert len(res_ws.evidence_items) == 1
    assert res_ws.evidence_items[0].metadata["normalized_fields"]["amount"] == "500.00"


def test_csv_adapter_nonexistent_file(csv_adapter: BankCSVAdapter) -> None:
    result = csv_adapter.ingest_file("nonexistent_path_xyz.csv")
    assert result.status == IngestionStatus.INVALID_INPUT
    assert "not found" in result.errors[0].message.lower()
