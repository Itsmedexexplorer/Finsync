"""Unit tests for TextMessageAdapter in VERITY Ingestion subsystem."""

from pathlib import Path
import pytest

from backend.domain.evidence import EvidenceModality, EvidenceSourceType
from backend.ingestion.result import IngestionStatus
from backend.ingestion.text_adapter import TextMessageAdapter


@pytest.fixture
def text_adapter() -> TextMessageAdapter:
    return TextMessageAdapter()


def test_text_adapter_single_english_message(text_adapter: TextMessageAdapter) -> None:
    msg = "Payment of Rs 18,500 received for Invoice #INV-102."
    result = text_adapter.ingest_payload(msg, source_name="sms_alert.txt")

    assert result.status == IngestionStatus.SUCCESS
    assert len(result.evidence_items) == 1
    ev = result.evidence_items[0]
    assert ev.modality == EvidenceModality.MESSAGING_CHAT
    assert ev.raw_payload == msg
    assert ev.language_hint == "en"
    assert len(ev.content_hash) == 64


def test_text_adapter_hinglish_detection(text_adapter: TextMessageAdapter) -> None:
    msg = "Bhai 20k GPay kar diya check kar lo, remaining agle hafte bhej dunga."
    result = text_adapter.ingest_payload(msg, source_name="whatsapp_snippet.txt")

    assert result.status == IngestionStatus.SUCCESS
    ev = result.evidence_items[0]
    assert ev.language_hint == "hinglish"
    assert ev.raw_payload == msg


def test_text_adapter_devanagari_and_tamil(text_adapter: TextMessageAdapter) -> None:
    # Hindi in Devanagari script
    hindi_msg = "नमस्ते, मैंने बीस हज़ार रुपये गूगल पे कर दिए हैं।"
    res_hi = text_adapter.ingest_payload(hindi_msg, source_name="hindi_chat.txt")
    assert res_hi.status == IngestionStatus.SUCCESS
    assert res_hi.evidence_items[0].language_hint == "hi"

    # Tamil script
    tamil_msg = "வணக்கம், பணம் அனுப்பப்பட்டது."
    res_ta = text_adapter.ingest_payload(tamil_msg, source_name="tamil_chat.txt")
    assert res_ta.status == IngestionStatus.SUCCESS
    assert res_ta.evidence_items[0].language_hint == "ta"


def test_text_adapter_multiline_whatsapp_export(text_adapter: TextMessageAdapter, tmp_path: Path) -> None:
    chat_content = """[15/08/2026, 11:20:10] Ramesh Sharma: Bhai 35,000 GPay kar diya check kar lo
[15/08/2026, 11:22:45] You: Thanks Rameshji, received Rs 35,000.
[16/08/2026, 14:05:00] Pooja Plastics: Sent Rs 1,25,000 via NEFT.
"""
    chat_file = tmp_path / "whatsapp_export.txt"
    chat_file.write_text(chat_content, encoding="utf-8")

    result = text_adapter.ingest_file(chat_file)
    assert result.status == IngestionStatus.SUCCESS
    assert len(result.evidence_items) == 3

    ev1 = result.evidence_items[0]
    assert ev1.metadata["sender"] == "Ramesh Sharma"
    assert "15/08/2026, 11:20:10" in ev1.metadata["timestamp_hint"]
    assert "Bhai 35,000 GPay" in ev1.raw_payload


def test_text_adapter_empty_and_nonexistent(text_adapter: TextMessageAdapter) -> None:
    # Empty
    res_empty = text_adapter.ingest_payload("   ", source_name="empty.txt")
    assert res_empty.status == IngestionStatus.INVALID_INPUT

    # Non-existent file
    res_missing = text_adapter.ingest_file("non_existent_chat.txt")
    assert res_missing.status == IngestionStatus.INVALID_INPUT
