"""Integration check against every real file in settings.archive_dir and
settings.test_data_dir (not in the repo, and their contents change while testing the bot)."""

import pytest

from forest_bot.application.ingest.extractors import ocr
from forest_bot.application.ingest.ingest import parse_file
from forest_bot.settings import settings

DATA_DIRS = (settings.archive_dir, settings.test_data_dir)
FILES = sorted(p for d in DATA_DIRS if d.exists() for p in d.iterdir() if p.is_file())

pytestmark = pytest.mark.skipif(not FILES, reason=f"no files in {DATA_DIRS}")


class ScannedPage(Exception):
    pass


def _refuse(image):
    """Stops at the first scanned page: OCR quality is tested in test_ocr_archive.py."""
    raise ScannedPage


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_file_parses_or_is_a_scan(path, monkeypatch):
    monkeypatch.setattr(ocr, "recognize", _refuse)
    try:
        document = parse_file(path.read_bytes(), path.name)
    except ScannedPage:
        assert path.suffix == ".pdf"
        return
    assert document.text
