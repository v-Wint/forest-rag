"""OCR for scanned PDF pages: Tesseract with the Ukrainian language pack."""

from dataclasses import dataclass
from statistics import fmean
from typing import Any

import pytesseract
from PIL import Image, ImageOps

from forest_bot.settings import settings

if settings.tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd


@dataclass(frozen=True, slots=True)
class OcrResult:
    text: str  # one visual line per line
    confidence: float  # mean word confidence, 0–100


def check_available() -> None:
    """Fail at startup, not on the first scanned upload, if Tesseract or its data is missing."""
    missing = set(settings.ocr_lang.split("+")) - set(pytesseract.get_languages())
    if missing:
        raise RuntimeError(f"Tesseract language data not installed: {sorted(missing)}")


def recognize(image: Image.Image) -> OcrResult:
    """The most confident reading over settings.ocr_thresholds."""
    return max(
        (_recognize_at(image, threshold) for threshold in settings.ocr_thresholds),
        key=lambda result: result.confidence,
    )


def _recognize_at(image: Image.Image, threshold: int) -> OcrResult:
    data = pytesseract.image_to_data(
        binarize(image, threshold), lang=settings.ocr_lang, output_type=pytesseract.Output.DICT
    )
    return words_to_result(data)


def binarize(image: Image.Image, threshold: int) -> Image.Image:
    """Keep only dark print: the textured background is lighter than the text."""
    # One entry per gray level: darker than the threshold → black, the rest → white.
    return ImageOps.grayscale(image).point([0] * threshold + [255] * (256 - threshold))


def words_to_result(data: dict[str, list[Any]]) -> OcrResult:
    """Rebuild text from Tesseract's word table: words → lines, lines → paragraphs."""
    paragraphs: dict[tuple[int, int], dict[int, list[str]]] = {}
    confidences: list[float] = []
    columns = ("block_num", "par_num", "line_num", "text", "conf")
    for block, paragraph, line, word, confidence in zip(*(data[c] for c in columns), strict=True):
        # Rows for pages, blocks and lines themselves have confidence -1 and no text.
        if str(word).strip() and float(confidence) >= 0:
            paragraphs.setdefault((block, paragraph), {}).setdefault(line, []).append(word)
            confidences.append(float(confidence))

    text = "\n\n".join(
        "\n".join(" ".join(words) for words in lines.values()) for lines in paragraphs.values()
    )
    return OcrResult(text=text, confidence=fmean(confidences) if confidences else 0.0)
