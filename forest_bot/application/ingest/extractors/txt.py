"""Plain text in any of the encodings animals' editors produce."""

import codecs

from forest_bot.application.ingest.errors import ExtractionError, FailureReason
from forest_bot.domain import ExtractedText
from forest_bot.domain.enums import ExtractionMethod, FileKind


def extract_txt(data: bytes) -> ExtractedText:
    return ExtractedText(
        text=_decode(data), file_kind=FileKind.TXT, method=ExtractionMethod.PLAIN_TEXT
    )


def _decode(data: bytes) -> str:
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        encodings = ["utf-16"]
    else:
        encodings = ["utf-8-sig", "cp1251"]  # UTF-8 (BOM optional), then legacy Windows Cyrillic
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ExtractionError(FailureReason.UNSUPPORTED, "text in an unknown encoding")
