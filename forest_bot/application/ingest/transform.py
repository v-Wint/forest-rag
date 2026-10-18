"""Read, second half: extracted text → a clean, validated ParsedDocument.

normalize_text() cleans the text up (look-alike characters, lines a PDF broke mid-sentence);
transform() checks it and adds the title and the content hash."""

import hashlib
import re
import unicodedata
from pathlib import PurePath

from forest_bot.application.ingest.errors import ExtractionError, FailureReason
from forest_bot.domain import ExtractedText, ParsedDocument
from forest_bot.settings import settings

_CHAR_MAP = str.maketrans(
    {
        # Ukrainian apostrophe comes in several look-alike code points; unify them so the
        # same word always produces the same text, hash and embedding.
        "’": "'",  # ’
        "ʼ": "'",  # ʼ
        "‘": "'",  # ‘
        "`": "'",
        " ": " ",  # no-break space
        " ": " ",  # narrow no-break space
        "­": None,  # soft hyphen
        "​": None,  # zero-width space
        "﻿": None,  # stray BOM
    }
)
_BULLET = re.compile(r"^[-–—•*]\s")
_NUMBERED = re.compile(r"^\d+[.)]\s")
_SENTENCE_END = ".!?:;"


def transform(extracted: ExtractedText, filename: str) -> ParsedDocument:
    text = normalize_text(extracted.text, reflow=extracted.needs_reflow)
    if not text:
        raise ExtractionError(FailureReason.EMPTY, "no text in the file")
    if len(text) > settings.max_text_chars:
        raise ExtractionError(FailureReason.TOO_LARGE, f"text is {len(text)} characters")

    return ParsedDocument(
        source_filename=filename,
        file_kind=extracted.file_kind,
        extraction_method=extracted.method,
        title=title_from_filename(filename),
        text=text,
        content_hash=content_hash(text),
        ocr_confidence=extracted.ocr_confidence,
    )


def content_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


def title_from_filename(filename: str) -> str:
    """The file name is the document's title: the text's first line can be anything (OCR
    reads a scan's decorative top as junk such as "1"). Telegram clients often send
    underscores for spaces."""
    return " ".join(PurePath(filename).stem.replace("_", " ").split()) or filename


def normalize_text(text: str, *, reflow: bool) -> str:
    """Clean up extracted text; with `reflow`, also rejoin visual lines into paragraphs."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").translate(_CHAR_MAP)
    text = text.replace("--", "—")  # OCR reads the em dash as a double hyphen
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    if reflow:
        lines = _reflow(lines)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _reflow(lines: list[str]) -> list[str]:
    """Rejoin lines that a PDF (or OCR) broke mid-sentence.

    PDFs store visual lines, not paragraphs. A line continues the previous one when it
    clearly cannot start a new block: it begins with a lowercase letter, or the previous
    line ends with a comma or dash. Headings and list items start uppercase or with a
    bullet, so they stay on their own lines.
    """
    result: list[str] = []
    for line in lines:
        if result and result[-1] and line and _continues(result[-1], line):
            result[-1] = _join(result[-1], line)
        else:
            result.append(line)
    return result


def _continues(previous: str, line: str) -> bool:
    if _BULLET.match(line) or _NUMBERED.match(line):
        return False
    first = line[0]
    if first.islower() or previous.endswith((",", "—", "–", "-")):
        return True
    # "...здавати до\n1 числа", "...рукавичкою\n«Біля греблі»"
    return (first.isdigit() or first == "«") and previous[-1] not in _SENTENCE_END


def _join(previous: str, line: str) -> str:
    # "Жолудівка-\nсойка" keeps its hyphen without a space.
    if previous.endswith("-") and line[0].islower():
        return previous + line
    return f"{previous} {line}"
