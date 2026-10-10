"""Text and Messaging Chat Ingestion Adapter for VERITY.

Handles raw text strings, WhatsApp chat export logs, and SMS messages,
supporting multilingual scripts (Devanagari, Tamil, Kannada, etc.) and Hinglish.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.ingestion.base import BaseIngestionAdapter
from backend.ingestion.result import IngestionError, IngestionResult, IngestionStatus


class TextMessageAdapter(BaseIngestionAdapter):
    """Adapter for ingesting text messages, WhatsApp chat logs, and SMS into Evidence objects."""

    @property
    def supported_modalities(self) -> List[EvidenceModality]:
        return [EvidenceModality.MESSAGING_CHAT]

    @property
    def supported_extensions(self) -> List[str]:
        return [".txt", ".log", ".chat"]

    # Patterns for standard WhatsApp / SMS export lines
    # e.g. "[15/08/2026, 14:30:15] Ramesh Sharma: Bhai 20k GPay kar diya"
    # or "15/08/2026, 2:30 pm - Ramesh Sharma: Sent payment"
    WHATSAPP_PATTERN_BRACKETS = re.compile(
        r"^\[(?P<timestamp>\d{1,2}[/-]\d{1,2}[/-]\d{2,4}[,\s]+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APap][Mm])?)\]\s*(?P<sender>[^:]+?):\s*(?P<message>.*)$"
    )
    WHATSAPP_PATTERN_DASH = re.compile(
        r"^(?P<timestamp>\d{1,2}[/-]\d{1,2}[/-]\d{2,4}[,\s]+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APap][Mm])?)\s*-\s*(?P<sender>[^:]+?):\s*(?P<message>.*)$"
    )

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
            raw_content = ""
            for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
                try:
                    with open(path, "r", encoding=encoding) as f:
                        raw_content = f.read()
                    break
                except UnicodeDecodeError:
                    continue

            if not raw_content:
                return IngestionResult.create_failure(
                    status=IngestionStatus.INVALID_INPUT,
                    source_name=path.name,
                    message="Text file is empty or could not be decoded.",
                )

            st = source_type or (
                EvidenceSourceType.WHATSAPP_EXPORT
                if "whatsapp" in path.name.lower() or "chat" in path.name.lower()
                else EvidenceSourceType.SMS_TEXT
            )
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
                message=f"Failed to read text file: {exc}",
            )

    def ingest_payload(
        self,
        raw_content: Union[str, bytes],
        source_name: str = "direct_text",
        source_type: Optional[EvidenceSourceType] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        if isinstance(raw_content, bytes):
            try:
                text_content = raw_content.decode("utf-8")
            except UnicodeDecodeError:
                text_content = raw_content.decode("latin-1", errors="replace")
        else:
            text_content = raw_content

        text_content = text_content.strip()
        if not text_content:
            return IngestionResult.create_failure(
                status=IngestionStatus.INVALID_INPUT,
                source_name=source_name,
                message="Text payload is empty.",
            )

        st = source_type or EvidenceSourceType.WHATSAPP_EXPORT
        base_meta = metadata or {}
        lines = [line.strip() for line in text_content.splitlines() if line.strip()]

        # Check if the content is a multi-line WhatsApp chat export
        parsed_chat_turns = self._try_parse_chat_lines(lines)

        if parsed_chat_turns:
            evidence_items: List[Evidence] = []
            for idx, (raw_line, timestamp_str, sender, msg) in enumerate(parsed_chat_turns, start=1):
                ev_id = f"EVID-TXT-{uuid.uuid4().hex[:8]}-M{idx:03d}"
                lang_hint = self._detect_language_hint(msg)
                
                item_meta = {
                    **base_meta,
                    "source_name": source_name,
                    "message_index": idx,
                    "sender": sender,
                    "timestamp_hint": timestamp_str,
                }
                
                ev = Evidence(
                    id=ev_id,
                    modality=EvidenceModality.MESSAGING_CHAT,
                    source_type=st,
                    source_name=f"{source_name}:Msg{idx}",
                    raw_payload=raw_line,
                    language_hint=lang_hint,
                    metadata=item_meta,
                )
                evidence_items.append(ev)

            return IngestionResult.create_success(
                evidence_items=evidence_items,
                source_name=source_name,
                metadata={
                    **base_meta,
                    "source_name": source_name,
                    "total_messages_parsed": len(evidence_items),
                },
            )
        else:
            # Standalone single message or multi-line block without WhatsApp timestamps
            ev_id = f"EVID-TXT-{uuid.uuid4().hex[:8]}"
            lang_hint = self._detect_language_hint(text_content)
            
            ev = Evidence(
                id=ev_id,
                modality=EvidenceModality.MESSAGING_CHAT,
                source_type=st,
                source_name=source_name,
                raw_payload=text_content,
                language_hint=lang_hint,
                metadata=base_meta,
            )
            return IngestionResult.create_success(
                evidence_items=[ev],
                source_name=source_name,
                metadata=base_meta,
            )

    def _try_parse_chat_lines(
        self,
        lines: List[str],
    ) -> List[Tuple[str, Optional[str], Optional[str], str]]:
        """Attempts to match structured chat lines with timestamp and sender."""
        results: List[Tuple[str, Optional[str], Optional[str], str]] = []
        matched_any = False

        for line in lines:
            m1 = self.WHATSAPP_PATTERN_BRACKETS.match(line)
            if m1:
                matched_any = True
                results.append((line, m1.group("timestamp"), m1.group("sender"), m1.group("message")))
                continue

            m2 = self.WHATSAPP_PATTERN_DASH.match(line)
            if m2:
                matched_any = True
                results.append((line, m2.group("timestamp"), m2.group("sender"), m2.group("message")))
                continue

            # If not a new header, append to the previous message if exists
            if results:
                prev_line, prev_ts, prev_sender, prev_msg = results[-1]
                updated_raw = f"{prev_line}\n{line}"
                updated_msg = f"{prev_msg}\n{line}"
                results[-1] = (updated_raw, prev_ts, prev_sender, updated_msg)

        return results if matched_any else []

    def _detect_language_hint(self, text: str) -> str:
        """Lightweight heuristic language hint detection for Indian linguistic contexts."""
        # Devanagari script range: U+0900 to U+097F
        if any("\u0900" <= ch <= "\u097f" for ch in text):
            return "hi"
        # Tamil script range: U+0B80 to U+0BFF
        if any("\u0b80" <= ch <= "\u0bff" for ch in text):
            return "ta"
        # Kannada script range: U+0C80 to U+0CFF
        if any("\u0c80" <= ch <= "\u0cff" for ch in text):
            return "kn"
        # Telugu script range: U+0C00 to U+0C7F
        if any("\u0c00" <= ch <= "\u0c7f" for ch in text):
            return "te"
        # Bengali script range: U+0980 to U+09FF
        if any("\u0980" <= ch <= "\u09ff" for ch in text):
            return "bn"

        # Hinglish / vernacular keywords in Latin script
        lower = text.lower()
        hinglish_tokens = {"bhai", "kar", "diya", "bhej", "raha", "hu", "karo", "lijiye", "gpay", "rupay", "hazar", "agle", "hafte", "pura", "paisa"}
        words = set(re.findall(r"\b\w+\b", lower))
        if len(words.intersection(hinglish_tokens)) >= 1:
            return "hinglish"

        return "en"
