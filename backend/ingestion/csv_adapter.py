"""Bank CSV Ingestion Adapter for VERITY.

Ingests heterogeneous Indian bank statement CSVs/TSVs, normalizes column aliases,
preserves raw row contents, and provides row-level error reporting.
"""

from __future__ import annotations

import csv
import io
import re
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

        try:
            all_rows = list(csv.reader(stream, delimiter=delimiter))
            header_idx = self._find_header_row(all_rows)
            reader = iter(all_rows[header_idx:])
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

        row_index = header_idx + 1  # 1-indexed file line of the header; data starts on the next line
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

    # Units and filler that banks add to column names: "Debit (INR)", "Amount in Rs.", "Balance (₹)"
    _UNIT_WORDS = re.compile(r"\b(?:inr|rs|rupees|in)\b|₹")

    @classmethod
    def _normalize_header(cls, header: str) -> str:
        text = re.sub(r"\([^)]*\)", " ", header.lower())  # drop "(INR)", "(₹)", "(Dr/Cr)"
        text = cls._UNIT_WORDS.sub(" ", text)
        return "".join(ch for ch in text if ch.isalnum())

    @classmethod
    def _classify_header(cls, header: str) -> Optional[str]:
        """Returns the canonical field a header stands for, or None (e.g. '#', 'Balance')."""
        n = cls._normalize_header(header)
        raw = header.lower()
        if not n or "balance" in n or n in ("sno", "srno", "slno", "serialno", "no"):
            return None
        if n in ("drcr", "crdr", "drcrindicator", "creditdebit", "debitcredit", "indicator", "direction", "crdrindicator"):
            return "drcr"
        if n in cls.DATE_SYNONYMS or n.endswith("date") or n == "dated":
            return "date"
        if n in ("credit", "cr", "deposit", "deposits", "credits", "moneyin", "creditamount", "depositamount") \
                or n.startswith("credit") or n.startswith("deposit"):
            return "credit"
        if n in ("debit", "dr", "withdrawal", "withdrawals", "debits", "moneyout", "debitamount", "withdrawalamount") \
                or n.startswith("debit") or n.startswith("withdraw"):
            return "debit"
        if n in cls.REF_SYNONYMS or any(k in n for k in ("utr", "rrn", "refno", "reference", "chq", "cheque", "txnid", "transactionid", "upiref")) \
                or re.search(r"\bref\b", raw):
            return "reference"
        if n in cls.NARRATION_SYNONYMS or any(k in n for k in ("narration", "description", "particular", "remark", "detail")):
            return "narration"
        if any(k in n for k in ("beneficiary", "payee", "payer", "remitter", "counterparty", "partyname", "party", "name", "paidto", "receivedfrom")):
            return "counterparty"
        if n in ("mode", "paymentmode", "txnmode", "transactionmode", "channel", "paymentmethod", "method", "type", "txntype", "transactiontype"):
            return "mode"
        if n in cls.AMOUNT_SYNONYMS or "amount" in n or n in ("amt", "value"):
            return "amount"
        return None

    def _detect_columns(self, headers: List[str]) -> Dict[str, str]:
        """Maps canonical field names (date, narration, amount, etc.) to the actual header names."""
        mapping: Dict[str, str] = {}
        for header in headers:
            field = self._classify_header(header)
            if field and field not in mapping:
                mapping[field] = header
        return mapping

    def _extract_normalized_fields(
        self,
        row_dict: Dict[str, str],
        column_mapping: Dict[str, str],
    ) -> Dict[str, Optional[str]]:
        """Extracts normalized key fields from the row dictionary."""
        fields: Dict[str, Optional[str]] = {
            "date": row_dict.get(column_mapping.get("date", ""), None),
            "narration": row_dict.get(column_mapping.get("narration", ""), None),
            "amount": row_dict.get(column_mapping.get("amount", ""), None),
            "credit": row_dict.get(column_mapping.get("credit", ""), None),
            "debit": row_dict.get(column_mapping.get("debit", ""), None),
            "reference": row_dict.get(column_mapping.get("reference", ""), None),
        }
        # Optional columns some banks export separately from the narration.
        if "counterparty" in column_mapping:
            fields["counterparty"] = row_dict.get(column_mapping["counterparty"]) or None
        if "mode" in column_mapping:
            fields["mode"] = row_dict.get(column_mapping["mode"]) or None
        if "drcr" in column_mapping:
            fields["drcr"] = row_dict.get(column_mapping["drcr"]) or None
        # No narration column: build one from mode / reference / party, the way banks write it.
        if not fields["narration"]:
            parts = [fields.get("mode"), fields.get("reference"), fields.get("counterparty")]
            built = "/".join(p.strip() for p in parts if p and p.strip())
            fields["narration"] = built or None
        return fields

    def _find_header_row(self, rows: List[List[str]]) -> int:
        """Index of the header row. Banks often put account details above the table."""
        for idx, row in enumerate(rows[:25]):
            cells = [c.strip() for c in row]
            mapping = self._detect_columns(cells)
            if "date" in mapping and any(k in mapping for k in ("amount", "credit", "debit")):
                return idx
        return 0
