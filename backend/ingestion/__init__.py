"""Evidence Ingestion subsystem for VERITY."""

from backend.ingestion.base import BaseIngestionAdapter
from backend.ingestion.csv_adapter import BankCSVAdapter
from backend.ingestion.image_adapter import ImagePaymentScreenshotAdapter
from backend.ingestion.pdf_adapter import PDFDocumentAdapter
from backend.ingestion.result import (
    IngestionError,
    IngestionResult,
    IngestionStatus,
)
from backend.ingestion.service import IngestionService
from backend.ingestion.text_adapter import TextMessageAdapter

__all__ = [
    "BaseIngestionAdapter",
    "BankCSVAdapter",
    "TextMessageAdapter",
    "PDFDocumentAdapter",
    "ImagePaymentScreenshotAdapter",
    "IngestionStatus",
    "IngestionError",
    "IngestionResult",
    "IngestionService",
]
