"""Unified Ingestion Service orchestrating multimodal financial evidence intake."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from backend.domain.evidence import Evidence, EvidenceSourceType
from backend.ingestion.base import BaseIngestionAdapter
from backend.ingestion.csv_adapter import BankCSVAdapter
from backend.ingestion.image_adapter import ImagePaymentScreenshotAdapter
from backend.ingestion.pdf_adapter import PDFDocumentAdapter
from backend.ingestion.result import IngestionError, IngestionResult, IngestionStatus
from backend.ingestion.text_adapter import TextMessageAdapter


class IngestionService:
    """Central service coordinating multimodal adapters for evidence normalization."""

    def __init__(self, adapters: Optional[List[BaseIngestionAdapter]] = None) -> None:
        self.adapters = adapters or [
            BankCSVAdapter(),
            TextMessageAdapter(),
            PDFDocumentAdapter(),
            ImagePaymentScreenshotAdapter(),
        ]

    def get_adapter_for_file(self, file_path: Union[Path, str]) -> Optional[BaseIngestionAdapter]:
        """Find the matching adapter for a given file path based on extension."""
        for adapter in self.adapters:
            if adapter.can_handle(file_path):
                return adapter
        return None

    def ingest_file(
        self,
        file_path: Union[Path, str],
        source_type: Optional[EvidenceSourceType] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        """Ingest a single evidence file from disk."""
        path = Path(file_path)
        if not path.exists():
            return IngestionResult.create_failure(
                status=IngestionStatus.INVALID_INPUT,
                source_name=str(path.name),
                message=f"File does not exist: {file_path}",
            )

        adapter = self.get_adapter_for_file(path)
        if not adapter:
            return IngestionResult.create_failure(
                status=IngestionStatus.UNSUPPORTED_FORMAT,
                source_name=path.name,
                message=f"No ingestion adapter registered for file extension '{path.suffix.lower()}'.",
            )

        return adapter.ingest_file(
            file_path=path,
            source_type=source_type,
            metadata=metadata,
        )

    def ingest_text(
        self,
        text: str,
        source_name: str = "direct_text",
        source_type: Optional[EvidenceSourceType] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        """Ingest raw text or chat message directly."""
        text_adapter = next(
            (a for a in self.adapters if isinstance(a, TextMessageAdapter)),
            TextMessageAdapter(),
        )
        return text_adapter.ingest_payload(
            raw_content=text,
            source_name=source_name,
            source_type=source_type or EvidenceSourceType.WHATSAPP_EXPORT,
            metadata=metadata,
        )

    def ingest_payload(
        self,
        raw_content: Union[str, bytes],
        source_name: str,
        source_type: Optional[EvidenceSourceType] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        """Ingest in-memory payload by detecting extension from source_name."""
        adapter = self.get_adapter_for_file(source_name)
        if not adapter:
            # Fallback to TextMessageAdapter if string, or return unsupported format
            if isinstance(raw_content, str):
                return self.ingest_text(
                    text=raw_content,
                    source_name=source_name,
                    source_type=source_type,
                    metadata=metadata,
                )
            return IngestionResult.create_failure(
                status=IngestionStatus.UNSUPPORTED_FORMAT,
                source_name=source_name,
                message=f"Unsupported format for payload '{source_name}'.",
            )

        return adapter.ingest_payload(
            raw_content=raw_content,
            source_name=source_name,
            source_type=source_type,
            metadata=metadata,
        )

    def ingest_batch(
        self,
        files_or_dir: Union[List[Union[Path, str]], Path, str],
        recursive: bool = False,
    ) -> IngestionResult:
        """Ingest a collection of files or an entire folder."""
        file_list: List[Path] = []

        if isinstance(files_or_dir, (str, Path)):
            p = Path(files_or_dir)
            if p.is_dir():
                pattern = "**/*" if recursive else "*"
                file_list = [f for f in sorted(p.glob(pattern)) if f.is_file()]
            elif p.is_file():
                file_list = [p]
            else:
                return IngestionResult.create_failure(
                    status=IngestionStatus.INVALID_INPUT,
                    source_name=str(files_or_dir),
                    message=f"Path not found: {files_or_dir}",
                )
        else:
            file_list = [Path(f) for f in files_or_dir]

        if not file_list:
            return IngestionResult.create_failure(
                status=IngestionStatus.INVALID_INPUT,
                source_name="batch_ingest",
                message="No files found to ingest in batch.",
            )

        combined_result: Optional[IngestionResult] = None
        for file_path in file_list:
            single_result = self.ingest_file(file_path)
            if combined_result is None:
                combined_result = single_result
            else:
                combined_result = combined_result.merge(single_result)

        return combined_result or IngestionResult.create_failure(
            status=IngestionStatus.INVALID_INPUT,
            source_name="batch_ingest",
            message="Batch ingestion produced no results.",
        )
