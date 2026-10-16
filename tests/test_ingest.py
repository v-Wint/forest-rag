import pytest

from forest_bot.application.etl import ExtractionError, FailureReason, parse_file

TEXT = "Членські внески\nВнесок — 4 жолуді з дорослого звіра на місяць."


def test_same_text_in_another_format_has_the_same_hash(make_docx):
    as_txt = parse_file(TEXT.encode(), "a.txt")
    as_docx = parse_file(make_docx(*TEXT.split("\n")), "b.docx")
    assert as_txt.content_hash == as_docx.content_hash


def test_empty_file_is_rejected():
    with pytest.raises(ExtractionError) as error:
        parse_file(b"  \n ", "empty.txt")
    assert error.value.reason is FailureReason.EMPTY
