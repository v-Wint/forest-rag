"""File format from content, not the name: a renamed file is still read correctly, and a
binary file renamed to .txt is rejected instead of being decoded into garbage."""

import codecs

from forest_bot.application.etl.errors import ExtractionError, FailureReason
from forest_bot.domain.enums import FileKind

_PDF_MAGIC = b"%PDF-"
_ZIP_MAGIC = b"PK\x03\x04"  # .docx is a zip; extract_docx checks it really is Word
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # legacy .doc / .xls / .ppt


def detect_file_kind(data: bytes) -> FileKind:
    if data.startswith(_PDF_MAGIC):
        return FileKind.PDF
    if data.startswith(_ZIP_MAGIC):
        return FileKind.DOCX
    if data.startswith(_OLE_MAGIC):
        raise ExtractionError(FailureReason.UNSUPPORTED, "legacy .doc; save it as .docx")
    if _looks_like_text(data):
        return FileKind.TXT
    raise ExtractionError(FailureReason.UNSUPPORTED, "unrecognised binary format")


def _looks_like_text(data: bytes) -> bool:
    sample = data[:8192]
    if sample.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return True
    if b"\x00" in sample:
        return False
    # Text has almost no control characters besides tab, newline, form feed, carriage return.
    control = sum(1 for b in sample if b < 32 and b not in (9, 10, 12, 13))
    return control <= len(sample) * 0.01
