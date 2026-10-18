import pytest

from forest_bot.application.ingest.extractors.ocr import words_to_result


def _table(rows):
    """rows: (block, paragraph, line, text, confidence) → Tesseract's DICT output shape."""
    keys = ["block_num", "par_num", "line_num", "text", "conf"]
    return {key: [row[i] for row in rows] for i, key in enumerate(keys)}


def test_rebuilds_lines_and_paragraphs():
    data = _table(
        [
            (1, 1, 1, "Членські", 95),
            (1, 1, 1, "внески", 93),
            (1, 2, 1, "Внесок", 90),
            (1, 2, 1, "4", 88),
            (1, 2, 2, "жолуді.", 92),
        ]
    )
    result = words_to_result(data)
    assert result.text == "Членські внески\n\nВнесок 4\nжолуді."
    assert result.confidence == pytest.approx(91.6)


def test_skips_structural_rows_and_blank_words():
    # Tesseract reports page/block/line rows with conf -1 and empty text.
    data = _table([(0, 0, 0, "", -1), (1, 1, 1, " ", 95), (1, 1, 1, "Слово", 80)])
    result = words_to_result(data)
    assert result.text == "Слово"
    assert result.confidence == 80


def test_empty_page():
    result = words_to_result(_table([(0, 0, 0, "", -1)]))
    assert result.text == ""
    assert result.confidence == 0
