"""Integration check against the real Forest Archive in settings.data_dir (not in the repo)."""

import pytest

from forest_bot.application.etl import parse_file
from forest_bot.application.etl.extractors import ocr
from forest_bot.settings import settings

DATA_DIR = settings.data_dir
ARCHIVE_FILES = sorted(DATA_DIR.glob("*.*")) if DATA_DIR.exists() else []

pytestmark = pytest.mark.skipif(not ARCHIVE_FILES, reason=f"archive not present in {DATA_DIR}")


class ScannedPage(Exception):
    pass


def _refuse(image):
    """Stops at the first scanned page: OCR quality is tested in test_ocr_archive.py."""
    raise ScannedPage


def test_every_archive_file_parses_or_is_a_scan(monkeypatch):
    monkeypatch.setattr(ocr, "recognize", _refuse)
    parsed, scanned = [], []
    for path in ARCHIVE_FILES:
        try:
            document = parse_file(path.read_bytes(), path.name)
        except ScannedPage:
            scanned.append(path.name)
            continue
        parsed.append(document)
        # The provisional title must match the file name, modulo «» quotes.
        assert document.title.replace("«", "").replace("»", "") == path.stem

    assert len(parsed) == 59
    assert len(scanned) == 19
    assert all(name.endswith(".pdf") for name in scanned)
    assert len({document.content_hash for document in parsed}) == len(parsed)
