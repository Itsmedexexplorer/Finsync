"""Unit tests for ImagePaymentScreenshotAdapter in VERITY Ingestion subsystem."""

from pathlib import Path
import pytest
from PIL import Image

from backend.domain.evidence import EvidenceModality, EvidenceSourceType
from backend.ingestion.image_adapter import ImagePaymentScreenshotAdapter
from backend.ingestion.result import IngestionStatus


@pytest.fixture
def image_adapter() -> ImagePaymentScreenshotAdapter:
    return ImagePaymentScreenshotAdapter()


def test_image_adapter_valid_png_and_jpg(image_adapter: ImagePaymentScreenshotAdapter, tmp_path: Path) -> None:
    # 1. Test PNG
    png_path = tmp_path / "payment_screenshot.png"
    img_png = Image.new("RGB", (400, 300), color=(100, 150, 200))
    img_png.save(png_path, format="PNG")

    res_png = image_adapter.ingest_file(png_path)
    assert res_png.status == IngestionStatus.SUCCESS
    assert len(res_png.evidence_items) == 1

    ev_png = res_png.evidence_items[0]
    assert ev_png.modality == EvidenceModality.PAYMENT_SCREENSHOT
    assert ev_png.metadata["width_px"] == 400
    assert ev_png.metadata["height_px"] == 300
    assert ev_png.metadata["image_format"] == "PNG"
    assert len(ev_png.content_hash) == 64

    # 2. Test JPG Receipt
    jpg_path = tmp_path / "store_receipt.jpg"
    img_jpg = Image.new("RGB", (250, 250), color=(255, 255, 255))
    img_jpg.save(jpg_path, format="JPEG")

    res_jpg = image_adapter.ingest_file(jpg_path)
    assert res_jpg.status == IngestionStatus.SUCCESS
    assert res_jpg.evidence_items[0].modality == EvidenceModality.RECEIPT

    # 3. Test Cash Voucher JPG
    voucher_path = tmp_path / "petty_cash_voucher.jpg"
    img_voucher = Image.new("RGB", (200, 200), color=(255, 255, 255))
    img_voucher.save(voucher_path, format="JPEG")

    res_voucher = image_adapter.ingest_file(voucher_path)
    assert res_voucher.status == IngestionStatus.SUCCESS
    assert res_voucher.evidence_items[0].modality == EvidenceModality.CASH_VOUCHER


def test_image_adapter_valid_webp(image_adapter: ImagePaymentScreenshotAdapter, tmp_path: Path) -> None:
    webp_path = tmp_path / "gpay_screen.webp"
    img = Image.new("RGB", (320, 480), color=(50, 50, 50))
    img.save(webp_path, format="WEBP")

    result = image_adapter.ingest_file(webp_path)
    assert result.status == IngestionStatus.SUCCESS
    assert result.evidence_items[0].metadata["image_format"] == "WEBP"


def test_image_adapter_corrupted_image(image_adapter: ImagePaymentScreenshotAdapter, tmp_path: Path) -> None:
    corrupted_path = tmp_path / "corrupted_screenshot.png"
    corrupted_path.write_bytes(b"\x89PNG\r\n\x1a\nCorrupted binary payload not a real image")

    result = image_adapter.ingest_file(corrupted_path)
    assert result.status == IngestionStatus.MALFORMED_DATA
    assert len(result.evidence_items) == 0
    assert len(result.errors) == 1


def test_image_adapter_unsupported_format(image_adapter: ImagePaymentScreenshotAdapter, tmp_path: Path) -> None:
    unsupported_path = tmp_path / "file.exe"
    unsupported_path.write_bytes(b"binary")

    result = image_adapter.ingest_file(unsupported_path)
    assert result.status == IngestionStatus.UNSUPPORTED_FORMAT
    assert len(result.errors) == 1
