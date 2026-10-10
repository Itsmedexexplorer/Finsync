"""API Security, Input Validation, and Resource Protection for VERITY."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional, Set
from fastapi import HTTPException, status

from backend.case_processing.models import CaseInput
from backend.config import Settings, get_settings


# Allowed file extensions supported by multimodal ingestion adapters
ALLOWED_EXTENSIONS: Set[str] = {
    ".csv",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".txt",
}

# Allowed MIME types for uploaded evidence
ALLOWED_MIME_TYPES: Set[str] = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "text/plain",
    "application/octet-stream", # for raw text / generic csv uploads
}


class SecurityValidator:
    """Reusable security validator for API request payloads and file uploads."""

    @staticmethod
    def sanitize_filename(filename: str, max_length: int = 255) -> str:
        """Sanitizes user-provided filename preventing path traversal, null bytes, and illegal chars."""
        if not filename:
            return "unnamed_evidence.txt"

        # 1. Remove null bytes
        clean_name = filename.replace("\0", "")

        # 2. Extract strictly the base name (prevents ../ or C:\ path traversal)
        clean_name = os.path.basename(clean_name)
        clean_name = Path(clean_name).name

        # 3. Strip illegal OS filename characters: < > : " / \ | ? *
        clean_name = re.sub(r'[<>:"/\\|?*]', '_', clean_name)

        # 4. Strip leading/trailing dots and whitespace
        clean_name = clean_name.strip(". \t\r\n")

        if not clean_name:
            clean_name = "sanitized_evidence.txt"

        # 5. Enforce length limit while preserving extension
        if len(clean_name) > max_length:
            stem = Path(clean_name).stem[:max_length - 10]
            suffix = Path(clean_name).suffix[:10]
            clean_name = f"{stem}{suffix}"

        return clean_name

    @staticmethod
    def validate_file_extension(filename: str) -> str:
        """Validates that the file extension is supported by VERITY ingestion adapters."""
        clean_name = SecurityValidator.sanitize_filename(filename)
        suffix = Path(clean_name).suffix.lower()

        if suffix not in ALLOWED_EXTENSIONS:
            allowed_list = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file format '{suffix or 'unknown'}'. Supported extensions: {allowed_list}.",
            )
        return suffix

    @staticmethod
    def validate_content_type(content_type: Optional[str], filename: str) -> None:
        """Validates the MIME content-type of an uploaded file."""
        if not content_type:
            return

        normalized_mime = content_type.lower().split(";")[0].strip()
        if normalized_mime not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported content type '{normalized_mime}' for file '{filename}'.",
            )

    @staticmethod
    def validate_file_size(size_bytes: int, max_bytes: int, filename: str = "") -> None:
        """Validates that an uploaded file does not exceed maximum byte limits."""
        if size_bytes > max_bytes:
            max_mb = max_bytes / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File '{filename}' exceeds maximum allowed size of {max_mb:.1f} MB (received {size_bytes / (1024 * 1024):.2f} MB).",
            )

    @staticmethod
    def validate_text_length(text: str, max_chars: int) -> None:
        """Validates that raw text input does not exceed character limits."""
        if len(text) > max_chars:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Text evidence exceeds maximum character limit of {max_chars:,} (received {len(text):,} characters).",
            )

    @staticmethod
    def validate_case_bounds(case_input: CaseInput, settings: Optional[Settings] = None) -> None:
        """Validates that case inputs stay within bounded complexity constraints."""
        cfg = settings or get_settings()

        if len(case_input.raw_file_paths) > cfg.max_files_per_case:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Case exceeds maximum allowed file count of {cfg.max_files_per_case} (received {len(case_input.raw_file_paths)}).",
            )

        if len(case_input.evidence_items) > cfg.max_evidence_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Case exceeds maximum evidence items limit of {cfg.max_evidence_items} (received {len(case_input.evidence_items)}).",
            )

        if len(case_input.transactions) > cfg.max_transactions_per_case:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Case exceeds maximum transactions limit of {cfg.max_transactions_per_case} (received {len(case_input.transactions)}).",
            )
