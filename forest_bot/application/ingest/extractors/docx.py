"""Word .docx: paragraphs and tables in document order."""

import io
import zipfile

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

from forest_bot.application.ingest.errors import ExtractionError, FailureReason
from forest_bot.domain import ExtractedText
from forest_bot.domain.enums import ExtractionMethod, FileKind
from forest_bot.settings import settings


def extract_docx(data: bytes) -> ExtractedText:
    _check_zip(data)
    try:
        document = docx.Document(io.BytesIO(data))
        blocks = [_block_text(block) for block in document.iter_inner_content()]
    except Exception as exc:  # untrusted input: any parser failure means a bad file
        raise ExtractionError(FailureReason.CORRUPT, f"cannot read .docx: {exc}") from exc
    return ExtractedText(
        text="\n".join(blocks), file_kind=FileKind.DOCX, method=ExtractionMethod.DOCX
    )


def _check_zip(data: bytes) -> None:
    """A Word document, not some other zip, and not a zip bomb."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
    except zipfile.BadZipFile as exc:
        raise ExtractionError(FailureReason.CORRUPT, f"damaged .docx: {exc}") from exc
    if not any(entry.filename == "word/document.xml" for entry in entries):
        raise ExtractionError(FailureReason.UNSUPPORTED, "zip file that is not a .docx")
    unpacked = sum(entry.file_size for entry in entries)
    if len(entries) > settings.max_docx_entries or unpacked > settings.max_docx_unpacked_bytes:
        raise ExtractionError(FailureReason.TOO_LARGE, f".docx unpacks to {unpacked} bytes")


def _block_text(block: Paragraph | Table) -> str:
    if isinstance(block, Table):
        return "\n".join(" | ".join(cell.text.strip() for cell in row.cells) for row in block.rows)
    return block.text
