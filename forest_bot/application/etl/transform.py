"""Transform: extracted text → a clean, validated ParsedDocument."""

import hashlib
from pathlib import PurePath

from forest_bot.application.etl.errors import ExtractionError, FailureReason
from forest_bot.application.etl.normalize import normalize_text
from forest_bot.domain import ExtractedText, ParsedDocument

MAX_TEXT_CHARS = 500_000
MAX_TITLE_CHARS = 200


def transform(extracted: ExtractedText, filename: str) -> ParsedDocument:
    text = normalize_text(extracted.text, reflow=extracted.needs_reflow)
    if not text:
        raise ExtractionError(FailureReason.EMPTY, "no text in the file")
    if len(text) > MAX_TEXT_CHARS:
        raise ExtractionError(FailureReason.TOO_LARGE, f"text is {len(text)} characters")

    return ParsedDocument(
        source_filename=filename,
        file_kind=extracted.file_kind,
        extraction_method=extracted.method,
        title=_title(text, filename),
        text=text,
        content_hash=content_hash(text),
        ocr_confidence=extracted.ocr_confidence,
    )


def content_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


def _title(text: str, filename: str) -> str:
    """First line of the text, else the file name. Provisional: the author confirms later."""
    first_line = text.split("\n", 1)[0].strip()
    if 0 < len(first_line) <= MAX_TITLE_CHARS:
        return first_line
    return PurePath(filename).stem
