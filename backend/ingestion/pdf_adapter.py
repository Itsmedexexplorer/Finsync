"""PDF Document Ingestion Adapter for VERITY.

Extracts text and metadata from PDF invoices, receipts, and bank statements using pypdf.
Accurately differentiates text-based digital PDFs from scanned image documents.
"""

from __future__ import annotations

import base64
import io
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pypdf
from PIL import Image

from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.ingestion.base import BaseIngestionAdapter
from backend.ingestion.csv_adapter import BankCSVAdapter
from backend.ingestion.pdf_statement import looks_like_statement, read_lines, statement_to_csv
from backend.ingestion.result import IngestionError, IngestionResult, IngestionStatus


class PDFDocumentAdapter(BaseIngestionAdapter):
    """Adapter for ingesting PDF files into canonical Evidence objects."""

    @property
    def supported_modalities(self) -> List[EvidenceModality]:
        return [
            EvidenceModality.INVOICE,
            EvidenceModality.RECEIPT,
            EvidenceModality.BANK_STATEMENT,
        ]

    @property
    def supported_extensions(self) -> List[str]:
        return [".pdf"]

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
                message=f"PDF file not found on disk: {file_path}",
            )

        try:
            with open(path, "rb") as f:
                pdf_bytes = f.read()

            if not pdf_bytes:
                return IngestionResult.create_failure(
                    status=IngestionStatus.INVALID_INPUT,
                    source_name=path.name,
                    message="PDF file is 0 bytes.",
                )

            st = source_type or (
                EvidenceSourceType.ZOHO_INVOICE
                if "invoice" in path.name.lower() or "inv" in path.name.lower()
                else EvidenceSourceType.BANK_PDF if "statement" in path.name.lower() or "bank" in path.name.lower()
                else EvidenceSourceType.MANUAL_UPLOAD
            )
            meta = metadata or {}
            meta["file_path"] = str(path.resolve())
            meta["file_size_bytes"] = len(pdf_bytes)

            return self.ingest_payload(
                raw_content=pdf_bytes,
                source_name=path.name,
                source_type=st,
                metadata=meta,
            )

        except Exception as exc:
            return IngestionResult.create_failure(
                status=IngestionStatus.MALFORMED_DATA,
                source_name=str(path.name),
                message=f"Failed to read PDF file: {exc}",
            )

    def ingest_payload(
        self,
        raw_content: Union[str, bytes],
        source_name: str = "document.pdf",
        source_type: Optional[EvidenceSourceType] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        if isinstance(raw_content, str):
            pdf_bytes = raw_content.encode("latin-1", errors="ignore")
        else:
            pdf_bytes = raw_content

        if not pdf_bytes:
            return IngestionResult.create_failure(
                status=IngestionStatus.INVALID_INPUT,
                source_name=source_name,
                message="PDF payload is empty.",
            )

        try:
            stream = io.BytesIO(pdf_bytes)
            reader = pypdf.PdfReader(stream)
            page_count = len(reader.pages)
        except Exception as exc:
            return IngestionResult.create_failure(
                status=IngestionStatus.MALFORMED_DATA,
                source_name=source_name,
                message=f"Corrupted or invalid PDF structure: {exc}",
            )

        if page_count == 0:
            return IngestionResult.create_failure(
                status=IngestionStatus.MALFORMED_DATA,
                source_name=source_name,
                message="PDF contains zero pages.",
            )

        extracted_pages: List[str] = []
        for p_num, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
                extracted_pages.append(page_text.strip())
            except Exception:
                extracted_pages.append("")

        full_extracted_text = "\n\n--- Page Break ---\n\n".join(
            p for p in extracted_pages if p
        ).strip()

        # Differentiate text-based PDF vs image/scanned PDF
        is_scanned = len(full_extracted_text) == 0

        # For scanned PDFs, attempt to extract embedded images from pages
        page_images_b64: List[Dict[str, Any]] = []
        if is_scanned:
            page_images_b64 = self._extract_page_images(reader)

        # Bank statements: turn the statement's table into bank rows, exactly like a CSV export.
        statement = self._read_statement(reader, full_extracted_text, page_images_b64, source_name, metadata)
        if statement is not None:
            return statement

        # Construct raw payload
        if is_scanned:
            raw_payload = f"[SCANNED_PDF_DOCUMENT: {source_name} | Pages: {page_count} | Size: {len(pdf_bytes)} bytes]"
        else:
            raw_payload = full_extracted_text

        # Determine appropriate modality
        modality = (
            EvidenceModality.BANK_STATEMENT
            if "statement" in source_name.lower() or "bank" in source_name.lower()
            else EvidenceModality.RECEIPT
            if "receipt" in source_name.lower()
            else EvidenceModality.INVOICE
        )

        st = source_type or EvidenceSourceType.MANUAL_UPLOAD
        base_meta = metadata or {}
        item_meta = {
            **base_meta,
            "source_name": source_name,
            "page_count": page_count,
            "is_scanned": is_scanned,
            "extracted_character_count": len(full_extracted_text),
            "pdf_info": {
                "title": str(reader.metadata.title) if reader.metadata and reader.metadata.title else None,
                "author": str(reader.metadata.author) if reader.metadata and reader.metadata.author else None,
            },
        }

        # Store extracted page images for VLM extraction (scanned PDFs only)
        if page_images_b64:
            item_meta["page_images_b64"] = page_images_b64

        evidence_id = f"EVID-PDF-{uuid.uuid4().hex[:8]}"
        ev = Evidence(
            id=evidence_id,
            modality=modality,
            source_type=st,
            source_name=source_name,
            raw_payload=raw_payload,
            metadata=item_meta,
        )

        return IngestionResult.create_success(
            evidence_items=[ev],
            source_name=source_name,
            metadata={
                **base_meta,
                "source_name": source_name,
                "page_count": page_count,
                "is_scanned": is_scanned,
                "page_images_extracted": len(page_images_b64),
            },
        )

    def _read_statement(
        self,
        reader: pypdf.PdfReader,
        plain_text: str,
        page_images_b64: List[Dict[str, Any]],
        source_name: str,
        metadata: Optional[Dict[str, Any]],
    ) -> Optional[IngestionResult]:
        """IngestionResult of bank rows when the PDF is a bank statement, else None."""
        csv_text: Optional[str] = None
        how = ""
        if plain_text:
            layout_pages = []
            for page in reader.pages:
                try:
                    layout_pages.append(page.extract_text(extraction_mode="layout") or "")
                except Exception:
                    layout_pages.append("")
            csv_text = statement_to_csv("\n".join(layout_pages), plain_text, source_name)
            how = "pdf_text"
        elif page_images_b64 and looks_like_statement("", source_name):
            # Scanned statement: read each page with OCR, then read rows line by line.
            from backend.extraction.ocr_extractor import ocr_available, read_image_text

            if ocr_available():
                try:
                    text = "\n".join(
                        read_image_text(base64.b64decode(p["image_b64"])) for p in page_images_b64[:10]
                    )
                    csv_text = read_lines(text)
                    how = "pdf_ocr"
                except Exception:
                    csv_text = None
        if not csv_text:
            return None

        result = BankCSVAdapter().ingest_payload(
            csv_text,
            source_name=source_name,
            source_type=EvidenceSourceType.BANK_CSV,
            metadata={**(metadata or {}), "statement_read_from": how},
        )
        return result if result.evidence_items else None

    def _extract_page_images(self, reader: pypdf.PdfReader) -> List[Dict[str, Any]]:
        """Extract embedded images from PDF pages for VLM extraction.

        Returns a list of dicts with 'page_number', 'image_b64', and 'mime_type'.
        """
        page_images: List[Dict[str, Any]] = []

        for page_num, page in enumerate(reader.pages, start=1):
            try:
                if not hasattr(page, "images") or not page.images:
                    continue

                for img_obj in page.images:
                    try:
                        img_data = img_obj.data
                        if not img_data or len(img_data) < 100:
                            continue

                        # Attempt to open and re-encode as PNG for consistent format
                        with Image.open(io.BytesIO(img_data)) as pil_img:
                            buf = io.BytesIO()
                            pil_img.save(buf, format="PNG")
                            png_bytes = buf.getvalue()

                        page_images.append({
                            "page_number": page_num,
                            "image_b64": base64.b64encode(png_bytes).decode("ascii"),
                            "mime_type": "image/png",
                            "width": pil_img.width if hasattr(pil_img, 'width') else None,
                            "height": pil_img.height if hasattr(pil_img, 'height') else None,
                        })
                        # Only extract the first/largest image per page to limit payload size
                        break
                    except Exception:
                        continue
            except Exception:
                continue

        return page_images
