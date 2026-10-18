import pytest

from forest_bot.application.ingest import ExtractionError, FailureReason
from forest_bot.application.ingest.transform import normalize_text, transform
from forest_bot.domain import ExtractedText
from forest_bot.domain.enums import ExtractionMethod, FileKind


def _extracted(text: str, *, needs_reflow: bool = False) -> ExtractedText:
    return ExtractedText(
        text=text,
        file_kind=FileKind.TXT,
        method=ExtractionMethod.PLAIN_TEXT,
        needs_reflow=needs_reflow,
    )


def test_title_is_the_file_name_not_the_first_line():
    # OCR read a scan's decorative top as "1": the file name says what the document is.
    document = transform(_extracted("1\nНебезпеки листяного лісу\nПід кронами…"), "Небезпеки.pdf")
    assert document.title == "Небезпеки"
    assert document.text == "1\nНебезпеки листяного лісу\nПід кронами…"


def test_underscores_in_the_file_name_become_spaces():
    document = transform(_extracted("Внесок — 4 жолуді."), "Членські_внески__На_узліссі.docx")
    assert document.title == "Членські внески На узліссі"


def test_same_text_wrapped_differently_has_same_hash():
    paragraphs = transform(_extracted("Здавати його треба до 20 числа."), "a.txt")
    wrapped = transform(_extracted("Здавати його\nтреба до 20 числа.", needs_reflow=True), "b.pdf")
    assert paragraphs.content_hash == wrapped.content_hash


def test_rejects_empty_document():
    with pytest.raises(ExtractionError) as error:
        transform(_extracted("  \n\n "), "empty.txt")
    assert error.value.reason is FailureReason.EMPTY


def test_reflow_joins_lines_broken_mid_sentence():
    raw = "Внесок становить 5 ягід. Здавати його\r\nтреба до 20 числа."
    assert normalize_text(raw, reflow=True) == (
        "Внесок становить 5 ягід. Здавати його треба до 20 числа."
    )


def test_reflow_keeps_headings_and_bullets_separate():
    raw = "Де шукати\n– Маслюки ростуть під\nсоснами.\n– Рижики в моху."
    assert normalize_text(raw, reflow=True) == (
        "Де шукати\n– Маслюки ростуть під соснами.\n– Рижики в моху."
    )


def test_reflow_joins_split_title_and_digit_continuation():
    raw = "Членські внески рукавички «Біля\nбобрової греблі»\nЗдавати до\n1 числа."
    assert normalize_text(raw, reflow=True) == (
        "Членські внески рукавички «Біля бобрової греблі»\nЗдавати до 1 числа."
    )


def test_reflow_keeps_hyphenated_compound_together():
    assert normalize_text("Жолудівка-\nсойка", reflow=True) == "Жолудівка-сойка"


def test_no_reflow_for_paragraph_sources():
    raw = "Перший рядок\nдругий рядок"
    assert normalize_text(raw, reflow=False) == raw


def test_unifies_apostrophes_and_invisible_characters():
    raw = "пам’ятка памʼятка сло­во​"
    assert normalize_text(raw, reflow=False) == "пам'ятка пам'ятка слово"


def test_collapses_blank_lines_and_spaces():
    raw = "  А   б  \n\n\n\nВ  "
    assert normalize_text(raw, reflow=False) == "А б\n\nВ"
