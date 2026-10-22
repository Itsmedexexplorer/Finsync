"""OCR reading for payment screenshots, photographed receipts and scanned PDFs.

OCR only turns the pixels of an image into plain text. That text is then handed to
the same deterministic extractors used for typed messages and text PDFs, so every
amount, reference and status is still decided by FinSync's fixed rules.

Uses the Tesseract engine (via ``pytesseract``). When Tesseract is not installed,
or OCR is switched off with ``VERITY_OCR_ENABLED=false``, ``is_available()`` is
False and the caller falls back to the previous behaviour (image kept as proof,
no amount read).
"""

from __future__ import annotations

import base64
import io
import logging
import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from PIL import Image, ImageOps

from backend.domain.evidence import Evidence
from backend.extraction.base import BaseExtractor
from backend.extraction.pdf_extractor import PDFDocumentExtractor
from backend.extraction.result import ExtractionResult, ExtractionStatus, ExtractionWarning
from backend.extraction.text_extractor import TextClaimExtractor

logger = logging.getLogger("verity.extraction.ocr")

# Only very small images are enlarged: payment apps already draw large text, and
# Tesseract reads oversized text worse, not better.
_MIN_WIDTH = 600
# Very large photos are shrunk first so reading stays fast on small servers.
_MAX_WIDTH = 2200
# Upper bound on pages read from one scanned PDF.
_MAX_PAGES = 5

# A rupee lookalike separated from its number by a space ("% 35,000").
_RUPEE_LOOKALIKE = re.compile(r"(?<![\w₹])[%~¥Z=?«<&€£]\s(?=\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?\b|\d+\.\d{2}\b)")


def _env_enabled() -> bool:
    return os.getenv("VERITY_OCR_ENABLED", "true").strip().lower() in ("true", "1", "yes")


@lru_cache(maxsize=1)
def _tesseract_ready() -> bool:
    try:
        import pytesseract  # noqa: WPS433 (optional dependency)

        pytesseract.get_tesseract_version()
        return True
    except Exception as exc:  # binary missing, not on PATH, or package missing
        logger.info("OCR unavailable (Tesseract not found): %s", exc)
        return False


def ocr_available() -> bool:
    """True when OCR is switched on and the Tesseract engine can be run."""
    return _env_enabled() and _tesseract_ready()


def prepare_image(img: Image.Image) -> Image.Image:
    """Cleans an image for reading: flatten transparency, grayscale, size, contrast, light background."""
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(background, img)
    gray = img.convert("L")

    width, height = gray.size
    if width > _MAX_WIDTH:
        scale = _MAX_WIDTH / width
        gray = gray.resize((_MAX_WIDTH, max(1, int(height * scale))), Image.LANCZOS)
    elif width < _MIN_WIDTH:
        scale = min(3.0, _MIN_WIDTH / max(1, width))
        gray = gray.resize((int(width * scale), int(height * scale)), Image.LANCZOS)

    gray = ImageOps.autocontrast(gray)  # no clipping: sparse pages have too few dark pixels
    # Dark-mode screenshots (light text on dark background) read far better inverted.
    histogram = gray.histogram()
    total = sum(histogram) or 1
    mean = sum(i * count for i, count in enumerate(histogram)) / total
    if mean < 110:
        gray = ImageOps.invert(gray)
    return gray


def clean_ocr_text(text: str) -> str:
    """Tidies OCR output: rupee-sign lookalikes, stray spacing and empty lines."""
    text = _RUPEE_LOOKALIKE.sub("₹", text)
    text = re.sub(r"₹\s+(?=\d)", "₹", text)
    # A comma read as a space right after the rupee sign: "₹1 25,000" → "₹1,25,000".
    text = re.sub(r"(₹\d{1,3})\s(?=\d{2,3}(?:,\d{2,3})*(?:\.\d{1,2})?\b)", r"\1,", text)
    lines = [re.sub(r"[ \t]{2,}", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


# --- The rupee sign --------------------------------------------------------------
# Tesseract's English model has no "₹", so it reads the sign as a lookalike: a symbol
# (% ~ ¥ Z …) or, worse, a digit (2, 7, 4…), which would turn ₹35,000 into 235,000.
# A word that starts with such a character and continues as a number is checked:
#   * a lookalike symbol is replaced by ₹;
#   * a leading digit is replaced only if its glyph has the rupee's shape (two
#     horizontal bars in the top half, nothing across the bottom, and a single
#     diagonal stroke drifting right at the bottom), or if the number is impossible
#     in Indian digit grouping without it (235,000 → ₹35,000).
_OCR_CONFIG = "--oem 1 --psm 4"  # one column of lines of varying size
_FALLBACK_CONFIG = "--oem 1 --psm 11"  # sparse text, tried when no amount was found
_SYMBOL_LEADS = set("%~¥Z=?«<&€£")
_AMOUNT_WORD = re.compile(r"^(?P<lead>.)(?P<num>\d{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)$")
_INDIAN_AMOUNT = re.compile(r"^(?:\d{1,3}|\d{1,2}(?:,\d{2})*,\d{3})(?:\.\d{1,2})?$")
_WESTERN_ONLY = re.compile(r"^\d{3}(?:,\d{3})+(?:\.\d{1,2})?$")


def looks_like_rupee(glyph: Image.Image) -> bool:
    """Shape test on one cropped glyph (dark text on a light background)."""
    g = glyph.convert("L")
    w, h = g.size
    px = g.load()
    dark = [[px[x, y] < 128 for x in range(w)] for y in range(h)]
    rows = [y for y in range(h) if any(dark[y])]
    cols = [x for x in range(w) if any(dark[y][x] for y in range(h))]
    if len(rows) < 8 or len(cols) < 4:
        return False
    y0, y1, x0, x1 = rows[0], rows[-1], cols[0], cols[-1]
    gw, gh = x1 - x0 + 1, y1 - y0 + 1

    bands, cur = [], None  # rows where ink covers at least half the glyph width
    for y in range(y0, y1 + 1):
        if sum(dark[y][x0:x1 + 1]) / gw >= 0.5:
            cur = cur or [y, y]
            cur[1] = y
        elif cur:
            bands.append(cur)
            cur = None
    if cur:
        bands.append(cur)
    centers = [((a + b) / 2 - y0) / gh for a, b in bands]
    if not centers or len([c for c in centers if c < 0.5]) < 2 or min(centers) >= 0.2:
        return False
    if any(c > 0.6 for c in centers):
        return False

    lows, single = [], True  # bottom third: one narrow stroke moving right
    for y in range(y0 + int(gh * 0.62), y1 + 1):
        xs = [x for x in range(x0, x1 + 1) if dark[y][x]]
        if not xs:
            continue
        gaps = sum(1 for a, b in zip(xs, xs[1:]) if b - a > 1)
        if gaps:
            single = False
        lows.append(((xs[0] + xs[-1]) / 2 - x0) / gw)
    drift = lows[-1] - lows[0] if len(lows) > 3 else 0.0
    return single and drift > 0.15


def _fix_rupee_word(word: str, glyph: Optional[Image.Image]) -> str:
    m = _AMOUNT_WORD.match(word)
    if not m:
        return word
    lead, num = m.group("lead"), m.group("num")
    if lead in _SYMBOL_LEADS:
        return "₹" + num
    if lead.isdigit():
        if glyph is not None and looks_like_rupee(glyph):
            return "₹" + num
        if _WESTERN_ONLY.match(word) and _INDIAN_AMOUNT.match(num):
            return "₹" + num
    return word


def _first_char_glyphs(
    prepared: Image.Image, words: List[Dict[str, int]], timeout: int, config: str,
) -> List[Optional[Image.Image]]:
    """Crops the first character of each given word box, using Tesseract's character boxes."""
    import pytesseract  # noqa: WPS433

    height = prepared.height
    boxes = []
    for line in pytesseract.image_to_boxes(prepared, lang="eng", config=config, timeout=timeout).splitlines():
        parts = line.split(" ")
        if len(parts) >= 5:
            x1, y1, x2, y2 = (int(v) for v in parts[1:5])
            boxes.append((x1, height - y2, x2, height - y1))  # to top-left origin
    crops: List[Optional[Image.Image]] = []
    for wb in words:
        inside = [
            b for b in boxes
            if wb["left"] - 2 <= (b[0] + b[2]) / 2 <= wb["left"] + wb["width"] + 2
            and wb["top"] - 2 <= (b[1] + b[3]) / 2 <= wb["top"] + wb["height"] + 2
        ]
        if not inside:
            crops.append(None)
            continue
        x1, y1, x2, y2 = min(inside, key=lambda b: b[0])
        crops.append(prepared.crop((max(0, x1 - 1), max(0, y1 - 1), x2 + 2, y2 + 2)))
    return crops


_HAS_AMOUNT = re.compile(r"(?:₹|Rs\.?|INR)\s?\d|\b\d{1,3}(?:,\d{2,3})+\b")


def _ocr_pass(prepared: Image.Image, config: str, timeout: int) -> str:
    import pytesseract  # noqa: WPS433

    data = pytesseract.image_to_data(
        prepared, lang="eng", config=config, timeout=timeout, output_type=pytesseract.Output.DICT,
    )
    words: List[Dict[str, Any]] = []
    for i, text in enumerate(data["text"]):
        text = (text or "").strip()
        if not text:
            continue
        words.append({
            "text": text,
            "line": (data["block_num"][i], data["par_num"][i], data["line_num"][i]),
            "left": data["left"][i], "top": data["top"][i],
            "width": data["width"][i], "height": data["height"][i],
        })

    # Only money-shaped words starting with a digit need their first glyph checked:
    # grouped or with paise (35,000 · 450.00), or a short number alone on its line (2450).
    # Dates, times and long UTR numbers are skipped, which saves an OCR pass on slow servers.
    per_line: Dict[Any, int] = {}
    for w in words:
        per_line[w["line"]] = per_line.get(w["line"], 0) + 1

    def money_shaped(w: Dict[str, Any]) -> bool:
        t = w["text"]
        if not (_AMOUNT_WORD.match(t) and t[0].isdigit()):
            return False
        return "," in t or "." in t or (per_line[w["line"]] == 1 and 3 <= len(t) <= 8)

    to_check = [w for w in words if money_shaped(w)]
    glyphs = _first_char_glyphs(prepared, to_check, timeout, config) if to_check else []
    glyph_of = {id(w): g for w, g in zip(to_check, glyphs)}
    for w in words:
        w["text"] = _fix_rupee_word(w["text"], glyph_of.get(id(w)))

    lines: Dict[Any, List[str]] = {}
    for w in words:
        lines.setdefault(w["line"], []).append(w["text"])
    return clean_ocr_text("\n".join(" ".join(ws) for ws in lines.values()))


def read_image_text(image_bytes: bytes, timeout: int = 25) -> str:
    """Runs OCR on raw image bytes and returns cleaned text ("" when nothing was read)."""
    with Image.open(io.BytesIO(image_bytes)) as img:
        prepared = prepare_image(img)
    text = _ocr_pass(prepared, _OCR_CONFIG, timeout)
    if not _HAS_AMOUNT.search(text):
        second = _ocr_pass(prepared, _FALLBACK_CONFIG, timeout)
        if _HAS_AMOUNT.search(second):
            return second
    return text


class OCRExtractor(BaseExtractor):
    """Reads text out of image evidence, then extracts claims with the deterministic rules."""

    def __init__(
        self,
        text_extractor: Optional[TextClaimExtractor] = None,
        pdf_extractor: Optional[PDFDocumentExtractor] = None,
    ) -> None:
        self.text_extractor = text_extractor or TextClaimExtractor()
        self.pdf_extractor = pdf_extractor or PDFDocumentExtractor()

    @property
    def provider_name(self) -> str:
        return "tesseract_ocr"

    def can_extract(self, evidence: Evidence) -> bool:
        meta = evidence.metadata or {}
        return bool(meta.get("image_bytes_b64") or meta.get("page_images_b64"))

    def is_available(self) -> bool:
        return ocr_available()

    def extract(
        self,
        evidence: Evidence,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExtractionResult:
        if not self.is_available():
            return ExtractionResult.create_failure(
                evidence_id=evidence.id,
                status=ExtractionStatus.PROVIDER_UNAVAILABLE,
                error_message="OCR engine (Tesseract) is not installed or is switched off.",
                provider_name=self.provider_name,
            )

        is_scanned_pdf = bool(evidence.metadata.get("page_images_b64"))
        try:
            text = self._read_text(evidence)
        except Exception as exc:  # a bad image or a timeout must never break the whole check
            logger.warning("OCR failed for %s: %s", evidence.source_name, exc)
            return ExtractionResult.create_failure(
                evidence_id=evidence.id,
                status=ExtractionStatus.REQUIRES_VISION_OR_OCR,
                error_message=f"Could not read text from the image: {exc}",
                provider_name=self.provider_name,
            )

        if not text.strip():
            return ExtractionResult.create_failure(
                evidence_id=evidence.id,
                status=ExtractionStatus.REQUIRES_VISION_OR_OCR,
                error_message="No readable text found in the image.",
                provider_name=self.provider_name,
            )

        # Same evidence, but with the text OCR read as its payload.
        meta = {**evidence.metadata, "ocr_text": text}
        meta.pop("is_scanned", None)
        read_ev = evidence.model_copy(update={"raw_payload": text, "metadata": meta})

        result = (
            self.pdf_extractor.extract(read_ev, context)
            if is_scanned_pdf
            else self.text_extractor.extract(read_ev, context)
        )
        if result.status not in (ExtractionStatus.SUCCESS, ExtractionStatus.PARTIAL_SUCCESS) or not result.claims:
            return ExtractionResult.create_failure(
                evidence_id=evidence.id,
                status=ExtractionStatus.NO_CLAIMS_FOUND,
                error_message="Text was read from the image, but it contains no payment details.",
                provider_name=self.provider_name,
            )

        # OCR can misread characters, so read claims carry slightly lower confidence.
        claims = [
            claim.model_copy(update={
                "confidence": round(min(claim.confidence, 0.95) * 0.9, 2),
                "metadata": {**(claim.metadata or {}), "read_by_ocr": True},
            })
            for claim in result.claims
        ]

        warnings: List[ExtractionWarning] = list(result.warnings or [])
        warnings.append(ExtractionWarning(
            message="Read from an image with OCR. Check the amount against the original image.",
            field="claimed_amount",
            raw_snippet=text[:300],
        ))

        return ExtractionResult.create_success(
            evidence_id=evidence.id,
            claims=claims,
            provider_name=f"{self.provider_name}+{result.provider_name}",
            confidence_score=min(c.confidence for c in claims),
            warnings=warnings,
            metadata={**(result.metadata or {}), "ocr_text": text[:2000]},
        )

    def _read_text(self, evidence: Evidence) -> str:
        meta = evidence.metadata
        if meta.get("image_bytes_b64"):
            return read_image_text(base64.b64decode(meta["image_bytes_b64"]))
        pages = [p for p in meta.get("page_images_b64") or [] if p.get("image_b64")][:_MAX_PAGES]
        texts = [read_image_text(base64.b64decode(p["image_b64"])) for p in pages]
        return "\n".join(t for t in texts if t)
