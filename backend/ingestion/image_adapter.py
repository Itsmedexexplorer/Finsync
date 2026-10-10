"""Image and Payment Screenshot Ingestion Adapter for VERITY.

Ingests PNG, JPG/JPEG, and WEBP payment screenshots and physical vouchers,
validates integrity, extracts technical dimensions/metadata, and creates canonical Evidence.
"""

from __future__ import annotations

import base64
import io
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from PIL import Image, UnidentifiedImageError

from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.ingestion.base import BaseIngestionAdapter
from backend.ingestion.result import IngestionError, IngestionResult, IngestionStatus


class ImagePaymentScreenshotAdapter(BaseIngestionAdapter):
    """Adapter for ingesting image files (PNG, JPG, WEBP) into Evidence objects."""

    @property
    def supported_modalities(self) -> List[EvidenceModality]:
        return [
            EvidenceModality.PAYMENT_SCREENSHOT,
            EvidenceModality.RECEIPT,
            EvidenceModality.CASH_VOUCHER,
        ]

    @property
    def supported_extensions(self) -> List[str]:
        return [".png", ".jpg", ".jpeg", ".webp"]

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
                message=f"Image file not found on disk: {file_path}",
            )

        ext = path.suffix.lower()
        if ext not in self.supported_extensions:
            return IngestionResult.create_failure(
                status=IngestionStatus.UNSUPPORTED_FORMAT,
                source_name=path.name,
                message=f"Unsupported image extension '{ext}'. Supported: {self.supported_extensions}",
            )

        try:
            with open(path, "rb") as f:
                img_bytes = f.read()

            if not img_bytes:
                return IngestionResult.create_failure(
                    status=IngestionStatus.INVALID_INPUT,
                    source_name=path.name,
                    message="Image file is 0 bytes.",
                )

            st = source_type or (
                EvidenceSourceType.WHATSAPP_EXPORT
                if "screenshot" in path.name.lower() or "whatsapp" in path.name.lower()
                else EvidenceSourceType.MANUAL_UPLOAD
            )
            meta = metadata or {}
            meta["file_path"] = str(path.resolve())
            meta["file_size_bytes"] = len(img_bytes)

            return self.ingest_payload(
                raw_content=img_bytes,
                source_name=path.name,
                source_type=st,
                metadata=meta,
            )

        except Exception as exc:
            return IngestionResult.create_failure(
                status=IngestionStatus.MALFORMED_DATA,
                source_name=str(path.name),
                message=f"Failed to read image file: {exc}",
            )

    def ingest_payload(
        self,
        raw_content: Union[str, bytes],
        source_name: str = "image.png",
        source_type: Optional[EvidenceSourceType] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        if isinstance(raw_content, str):
            img_bytes = raw_content.encode("latin-1", errors="ignore")
        else:
            img_bytes = raw_content

        if not img_bytes:
            return IngestionResult.create_failure(
                status=IngestionStatus.INVALID_INPUT,
                source_name=source_name,
                message="Image payload is empty.",
            )

        try:
            stream = io.BytesIO(img_bytes)
            with Image.open(stream) as img:
                img.verify()  # Verify image integrity
                
            # Reopen to read dimensions after verify()
            stream.seek(0)
            with Image.open(stream) as img:
                width, height = img.size
                img_format = img.format or "UNKNOWN"
                mode = img.mode

        except (UnidentifiedImageError, OSError, SyntaxError) as exc:
            return IngestionResult.create_failure(
                status=IngestionStatus.MALFORMED_DATA,
                source_name=source_name,
                message=f"Corrupted or invalid image content: {exc}",
            )

        # Classify modality based on naming cues
        lower_name = source_name.lower()
        if "voucher" in lower_name or "cash" in lower_name:
            modality = EvidenceModality.CASH_VOUCHER
        elif "receipt" in lower_name:
            modality = EvidenceModality.RECEIPT
        else:
            modality = EvidenceModality.PAYMENT_SCREENSHOT

        st = source_type or EvidenceSourceType.MANUAL_UPLOAD
        base_meta = metadata or {}

        # Determine MIME type for VLM providers
        mime_map = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
        mime_type = mime_map.get(img_format, f"image/{img_format.lower()}")

        item_meta = {
            **base_meta,
            "source_name": source_name,
            "image_format": img_format,
            "width_px": width,
            "height_px": height,
            "color_mode": mode,
            "file_size_bytes": len(img_bytes),
            "mime_type": mime_type,
            # Base64-encoded image data for VLM extraction — never used in financial calculations
            "image_bytes_b64": base64.b64encode(img_bytes).decode("ascii"),
        }

        raw_payload = (
            f"[IMAGE_ARTIFACT: {source_name} | Format: {img_format} | "
            f"Dimensions: {width}x{height}px | Mode: {mode} | Size: {len(img_bytes)} bytes]"
        )

        evidence_id = f"EVID-IMG-{uuid.uuid4().hex[:8]}"
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
                "width": width,
                "height": height,
                "format": img_format,
            },
        )
