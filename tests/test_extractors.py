import io

import pypdfium2 as pdfium
import pytest

from forest_bot.application.etl import ExtractionError, FailureReason
from forest_bot.application.etl.extractors import docx as docx_extractor
from forest_bot.application.etl.extractors import extract_docx, extract_pdf, extract_txt, ocr
from forest_bot.application.etl.extractors.ocr import OcrResult
from forest_bot.domain.enums import ExtractionMethod, FileKind

TEXT = "Членські внески\nВнесок — 4 жолуді з дорослого звіра на місяць."
BLANK = OcrResult(text="", confidence=0.0)  # what Tesseract gives for a page with no words


@pytest.fixture
def ocr_returns(monkeypatch):
    """Replace OCR with the given results, one per scanned page."""

    def script(*results: OcrResult) -> None:
        pages = iter(results)
        monkeypatch.setattr(ocr, "recognize", lambda image: next(pages))

    return script


def _blank_pdf(pages: int) -> bytes:
    pdf = pdfium.PdfDocument.new()
    for _ in range(pages):
        pdf.new_page(595, 842)
    buffer = io.BytesIO()
    pdf.save(buffer)
    return buffer.getvalue()


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "cp1251"])
def test_txt_in_common_encodings(encoding):
    extracted = extract_txt(TEXT.encode(encoding))
    assert extracted.text == TEXT
    assert extracted.file_kind is FileKind.TXT


def test_docx_paragraphs(make_docx):
    extracted = extract_docx(make_docx(*TEXT.split("\n")))
    assert extracted.text == TEXT
    assert extracted.method is ExtractionMethod.DOCX
    assert not extracted.needs_reflow


def test_docx_that_unpacks_too_large(make_docx, monkeypatch):
    monkeypatch.setattr(docx_extractor, "MAX_UNPACKED_BYTES", 1_000)
    with pytest.raises(ExtractionError) as error:
        extract_docx(make_docx("Порада"))
    assert error.value.reason is FailureReason.TOO_LARGE


def test_damaged_docx():
    with pytest.raises(ExtractionError) as error:
        extract_docx(b"PK\x03\x04 not really a zip")
    assert error.value.reason is FailureReason.CORRUPT


def test_damaged_pdf():
    with pytest.raises(ExtractionError) as error:
        extract_pdf(b"%PDF-1.7 broken")
    assert error.value.reason is FailureReason.CORRUPT


def test_blank_page_next_to_a_scan_is_skipped(ocr_returns):
    ocr_returns(OcrResult(TEXT, 90.0), BLANK)
    extracted = extract_pdf(_blank_pdf(2))
    assert extracted.text.strip() == TEXT
    assert extracted.method is ExtractionMethod.OCR
    assert extracted.ocr_confidence == 90.0


def test_blank_pdf_is_empty_not_an_unreadable_scan(ocr_returns):
    ocr_returns(BLANK)
    assert extract_pdf(_blank_pdf(1)).text == ""  # transform() then rejects it as EMPTY


def test_low_confidence_scan_is_rejected(ocr_returns):
    ocr_returns(OcrResult("Вн3с0к", 30.0))
    with pytest.raises(ExtractionError) as error:
        extract_pdf(_blank_pdf(1))
    assert error.value.reason is FailureReason.UNREADABLE_SCAN
