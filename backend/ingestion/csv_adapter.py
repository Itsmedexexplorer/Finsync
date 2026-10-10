"""Bank CSV Ingestion Adapter for VERITY.

Ingests heterogeneous Indian bank statement CSVs/TSVs, normalizes column aliases,
preserves raw row contents, and provides row-level error reporting.
"""

from __future__ import annotations

import csv
import io
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.ingestion.base import BaseIngestionAdapter
from backend.ingestion.result import IngestionError, IngestionResult, IngestionStatus


class BankCSVAdapter(BaseIngestionAdapter):
    """Adapter for ingesting Bank Statement CSV files into normalized Evidence objects."""

    @property
    def supported_modalities(self) -> List[EvidenceModality]:
        return [EvidenceModality.BANK_STATEMENT]

    @property
    def supported_extensions(self) -> List[str]:
        return [".csv", ".tsv"]

    # Canonical column synonym mappings for Indian banking exports
    DATE_SYNONYMS = {
        "date", "txndate", "txn_date", "transactiondate", "transaction_date",
        "valuedate", "value_date", "postingdate", "posting_date"
    }
    NARRATION_SYNONYMS = {
        "narration", "description", "particulars", "transactiondetails",
        "transaction_details", "remarks", "details", "memo", "description_narration"
    }
    AMOUNT_SYNONYMS = {
        "amount", "txnamount", "transactionamount", "transaction_amount",
        "netamount", "total_amount", "credit", "debit", "deposit", "withdrawal", "cr", "dr"
    }
    REF_SYNONYMS = {
        "ref", "refno", "ref_no", "reference", "referenceno", "reference_no",
        "utr", "rrn", "chqrefno", "chq_ref_no", "transactionid", "transaction_id",
        "chequeno", "cheque_number", "upi_rrn"
    }

    def ingest_file(
        self,
        file_path: Union[Path, str],
        source_type: Optional[EvidenceSourceType] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        path = Path(file_path)
        if not path.exists():
            return IngestionResult.create_failure(
                status=IngestionStatus.INVALID_INPUT,
                source_name=str(path.name),
                message=f"File not found on disk: {file_path}",
            )

        try:
            # Try reading with utf-8, fallback to latin-1 / cp1252 if needed
            raw_content = ""
            for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
                try:
                    with open(path, "r", encoding=encoding) as f:
                        raw_content = f.read()
                    break
                except UnicodeDecodeError:
                    continue

            if not raw_content:
                return IngestionResult.create_failure(
                    status=IngestionStatus.INVALID_INPUT,
                    source_name=str(path.name),
                    message="CSV file is empty or could not be decoded.",
                )

            st = source_type or EvidenceSourceType.BANK_CSV
            meta = metadata or {}
            meta["file_path"] = str(path.resolve())
            meta["file_size_bytes"] = path.stat().st_size
            return self.ingest_payload(
                raw_content=raw_content,
                source_name=path.name,
                source_type=st,
                metadata=meta,
            )

        except Exception as exc:
            return IngestionResult.create_failure(
                status=IngestionStatus.MALFORMED_DATA,
                source_name=str(path.name),
                message=f"Failed to read CSV file: {exc}",
            )

    def ingest_payload(
        self,
        raw_content: Union[str, bytes],
        source_name: str,
        source_type: Optional[EvidenceSourceType] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        if isinstance(raw_content, bytes):
            try:
                text_content = raw_content.decode("utf-8-sig")
            except UnicodeDecodeError:
                text_content = raw_content.decode("latin-1", errors="replace")
        else:
            text_content = raw_content

        text_content = text_content.strip()
        if not text_content:
            return IngestionResult.create_failure(
                status=IngestionStatus.INVALID_INPUT,
                source_name=source_name,
                message="CSV payload is completely empty.",
            )

        delimiter = "\t" if source_name.endswith(".tsv") or "\t" in text_content.splitlines()[0] else ","
        stream = io.StringIO(text_content)
        reader = csv.reader(stream, delimiter=delimiter)

        try:
            raw_header = next(reader, None)
        except Exception as exc:
            return IngestionResult.create_failure(
                status=IngestionStatus.MALFORMED_DATA,
                source_name=source_name,
                message=f"Failed to parse CSV header: {exc}",
            )

        if not raw_header or not any(raw_header):
            return IngestionResult.create_failure(
                status=IngestionStatus.INVALID_INPUT,
                source_name=source_name,
                message="CSV header row is empty.",
            )

        cleaned_headers = [h.strip() for h in raw_header]
        column_mapping = self._detect_columns(cleaned_headers)

        # Validate minimum essential headers (must at least identify Date or Narration or Amount)
        if not any(k in column_mapping for k in ("date", "narration", "amount", "credit", "debit")):
            return IngestionResult.create_failure(
                status=IngestionStatus.MALFORMED_DATA,
                source_name=source_name,
                message=(
                    f"CSV header row lacks recognizable banking columns. "
                    f"Detected headers: {cleaned_headers}"
                ),
                raw_data=delimiter.join(raw_header),
            )

        st = source_type or EvidenceSourceType.BANK_CSV
        base_meta = metadata or {}
        evidence_items: List[Evidence] = []
        errors: List[IngestionError] = []

        row_index = 1  # 1-indexed (header was row 1, data starts at 2)
        for raw_row in reader:
            row_index += 1
            if not raw_row or all(not cell.strip() for cell in raw_row):
                # Skip empty lines
                continue

            raw_row_str = delimiter.join(raw_row)
            
            # Check column count mismatch
            if len(raw_row) != len(cleaned_headers):
                errors.append(IngestionError(
                    source_name=source_name,
                    row_index=row_index,
                    error_type=IngestionStatus.MALFORMED_DATA,
                    message=f"Row column count mismatch: expected {len(cleaned_headers)} columns, got {len(raw_row)}.",
                    raw_data=raw_row_str,
                ))
                continue

            # Build row dict
            row_dict = {cleaned_headers[i]: raw_row[i].strip() for i in range(len(raw_row))}
            normalized_row = self._extract_normalized_fields(row_dict, column_mapping)

            # Validate basic row non-emptiness
            if not any(normalized_row.values()):
                errors.append(IngestionError(
                    source_name=source_name,
                    row_index=row_index,
                    error_type=IngestionStatus.MALFORMED_DATA,
                    message="Row contains no parseable data values.",
                    raw_data=raw_row_str,
                ))
                continue

            # Generate unique deterministic Evidence ID for the row
            evidence_id = f"EVID-CSV-{uuid.uuid4().hex[:8]}-R{row_index:04d}"
            
            row_meta = {
                **base_meta,
                "source_file": source_name,
                "row_index": row_index,
                "normalized_fields": normalized_row,
                "raw_columns": row_dict,
                "detected_headers": cleaned_headers,
            }

            ev = Evidence(
                id=evidence_id,
                modality=EvidenceModality.BANK_STATEMENT,
                source_type=st,
                source_name=f"{source_name}:Row{row_index}",
                raw_payload=raw_row_str,
                metadata=row_meta,
            )
            evidence_items.append(ev)

        total_rows = len(evidence_items) + len(errors)
        if total_rows == 0:
            return IngestionResult.create_failure(
                status=IngestionStatus.INVALID_INPUT,
                source_name=source_name,
                message="CSV contains headers but no data rows.",
            )

        if errors and not evidence_items:
            status = IngestionStatus.MALFORMED_DATA
        elif errors and evidence_items:
            status = IngestionStatus.PARTIAL_SUCCESS
        else:
            status = IngestionStatus.SUCCESS

        return IngestionResult(
            status=status,
            evidence_items=evidence_items,
            errors=errors,
            warnings=[],
            metadata={
                **base_meta,
                "source_name": source_name,
                "total_records": total_rows,
                "successful_records": len(evidence_items),
                "failed_records": len(errors),
                "detected_headers": cleaned_headers,
            },
        )

    def _detect_columns(self, headers: List[str]) -> Dict[str, str]:
        """Maps canonical field names (date, narration, amount, etc.) to the actual header names."""
        mapping: Dict[str, str] = {}
        for header in headers:
            normalized = "".join(filter(str.isalnum, header)).lower()
            if normalized in self.DATE_SYNONYMS and "date" not in mapping:
                mapping["date"] = header
            elif normalized in self.NARRATION_SYNONYMS and "narration" not in mapping:
                mapping["narration"] = header
            elif normalized in self.REF_SYNONYMS and "reference" not in mapping:
                mapping["reference"] = header
            elif normalized in ("credit", "cr", "deposit") and "credit" not in mapping:
                mapping["credit"] = header
            elif normalized in ("debit", "dr", "withdrawal") and "debit" not in mapping:
                mapping["debit"] = header
            elif normalized in self.AMOUNT_SYNONYMS and "amount" not in mapping:
                mapping["amount"] = header
        return mapping

    def _extract_normalized_fields(
        self,
        row_dict: Dict[str, str],
        column_mapping: Dict[str, str],
    ) -> Dict[str, Optional[str]]:
        """Extracts normalized key fields from the row dictionary."""
        return {
            "date": row_dict.get(column_mapping.get("date", ""), None),
            "narration": row_dict.get(column_mapping.get("narration", ""), None),
            "amount": row_dict.get(column_mapping.get("amount", ""), None),
            "credit": row_dict.get(column_mapping.get("credit", ""), None),
            "debit": row_dict.get(column_mapping.get("debit", ""), None),
            "reference": row_dict.get(column_mapping.get("reference", ""), None),
        }
