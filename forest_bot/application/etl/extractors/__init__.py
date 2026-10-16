"""Extract: file bytes → raw text, with one extractor per format, picked by content."""

from forest_bot.application.etl.errors import ExtractionError, FailureReason
from forest_bot.application.etl.extractors.detect import detect_file_kind
from forest_bot.application.etl.extractors.docx import extract_docx
from forest_bot.application.etl.extractors.pdf import extract_pdf
from forest_bot.application.etl.extractors.txt import extract_txt
from forest_bot.domain import ExtractedText
from forest_bot.domain.enums import FileKind

MAX_FILE_BYTES = 20 * 1024 * 1024  # Telegram bots cannot download more anyway

EXTRACTORS = {
    FileKind.TXT: extract_txt,
    FileKind.DOCX: extract_docx,
    FileKind.PDF: extract_pdf,
}


def extract(data: bytes) -> ExtractedText:
    if len(data) > MAX_FILE_BYTES:
        raise ExtractionError(FailureReason.TOO_LARGE, f"file is {len(data)} bytes")
    kind = detect_file_kind(data)
    return EXTRACTORS[kind](data)
