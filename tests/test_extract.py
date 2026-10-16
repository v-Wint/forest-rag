import io
import zipfile

import pytest

import forest_bot.application.etl.extractors as extractors
from forest_bot.application.etl import ExtractionError, FailureReason, extract
from forest_bot.domain.enums import FileKind

TEXT = "Внесок — 4 жолуді."


def _fails_with(reason: FailureReason, data: bytes) -> None:
    with pytest.raises(ExtractionError) as error:
        extract(data)
    assert error.value.reason is reason


def test_picks_extractor_by_content(make_docx):
    assert extract(make_docx("Порада")).file_kind is FileKind.DOCX
    assert extract(TEXT.encode()).file_kind is FileKind.TXT


def test_rejects_oversized_file(monkeypatch):
    monkeypatch.setattr(extractors, "MAX_FILE_BYTES", 10)
    _fails_with(FailureReason.TOO_LARGE, TEXT.encode())


def test_rejects_legacy_doc():
    _fails_with(FailureReason.UNSUPPORTED, b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + bytes(100))


def test_rejects_binary_disguised_as_text():
    _fails_with(FailureReason.UNSUPPORTED, bytes(range(256)) * 10)


def test_rejects_non_docx_zip():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/workbook.xml", "<workbook/>")
    _fails_with(FailureReason.UNSUPPORTED, buffer.getvalue())
