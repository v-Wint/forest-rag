import pytest

from forest_bot.application.etl import ExtractionError, FailureReason, transform
from forest_bot.domain import ExtractedText
from forest_bot.domain.enums import ExtractionMethod, FileKind


def _extracted(text: str, *, needs_reflow: bool = False) -> ExtractedText:
    return ExtractedText(
        text=text,
        file_kind=FileKind.TXT,
        method=ExtractionMethod.PLAIN_TEXT,
        needs_reflow=needs_reflow,
    )


def test_title_is_the_first_line():
    document = transform(_extracted("Членські внески\nВнесок — 4 жолуді."), "внески.txt")
    assert document.title == "Членські внески"
    assert document.text == "Членські внески\nВнесок — 4 жолуді."


def test_title_falls_back_to_file_name():
    document = transform(_extracted("Дуже " * 100), "Довга порада.txt")
    assert document.title == "Довга порада"


def test_same_text_wrapped_differently_has_same_hash():
    paragraphs = transform(_extracted("Здавати його треба до 20 числа."), "a.txt")
    wrapped = transform(_extracted("Здавати його\nтреба до 20 числа.", needs_reflow=True), "b.pdf")
    assert paragraphs.content_hash == wrapped.content_hash


def test_rejects_empty_document():
    with pytest.raises(ExtractionError) as error:
        transform(_extracted("  \n\n "), "empty.txt")
    assert error.value.reason is FailureReason.EMPTY
