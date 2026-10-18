"""PDF: the text layer where a page has one, OCR where the page is a scanned image."""

from dataclasses import dataclass

import pypdfium2 as pdfium

from forest_bot.application.ingest.errors import ExtractionError, FailureReason
from forest_bot.application.ingest.extractors import ocr
from forest_bot.domain import ExtractedText
from forest_bot.domain.enums import ExtractionMethod, FileKind
from forest_bot.settings import settings


@dataclass(frozen=True, slots=True)
class _Page:
    text: str
    ocr_confidence: float | None = None  # None: read from the text layer, or blank


def extract_pdf(data: bytes) -> ExtractedText:
    try:
        with pdfium.PdfDocument(data) as pdf:
            if len(pdf) > settings.max_pdf_pages:
                raise ExtractionError(FailureReason.TOO_LARGE, f"PDF has {len(pdf)} pages")
            pages = [_read_page(page, number) for number, page in enumerate(pdf, start=1)]
    except pdfium.PdfiumError as exc:
        raise ExtractionError(FailureReason.CORRUPT, f"damaged or encrypted PDF: {exc}") from exc

    confidences = [page.ocr_confidence for page in pages if page.ocr_confidence is not None]
    return ExtractedText(
        text="\n\n".join(page.text for page in pages),
        file_kind=FileKind.PDF,
        method=_method(pages),
        needs_reflow=True,
        ocr_confidence=min(confidences, default=None),
    )


def _read_page(page: pdfium.PdfPage, number: int) -> _Page:
    text = page.get_textpage().get_text_bounded()
    if sum(ch.isalpha() for ch in text) >= settings.min_letters_for_text_layer:
        return _Page(text)

    # PDF units are 1/72 inch. (pypdfium2 has no type hints; `scale` is a float.)
    scale = settings.ocr_render_dpi / 72
    image = page.render(scale=scale).to_pil()  # type: ignore[arg-type]
    result = ocr.recognize(image)
    # No words at all is a blank page (e.g. the last page of a Word export), not a bad scan.
    if not result.text.strip():
        return _Page("")
    if result.confidence < settings.ocr_min_confidence:
        raise ExtractionError(
            FailureReason.UNREADABLE_SCAN,
            f"page {number} read with confidence {result.confidence:.0f}",
        )
    return _Page(result.text, result.confidence)


def _method(pages: list[_Page]) -> ExtractionMethod:
    scanned = any(page.ocr_confidence is not None for page in pages)
    text_layer = any(page.ocr_confidence is None and page.text for page in pages)
    if scanned and text_layer:
        return ExtractionMethod.PDF_MIXED
    return ExtractionMethod.OCR if scanned else ExtractionMethod.PDF_TEXT_LAYER
