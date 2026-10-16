from forest_bot.application.etl.normalize import normalize_text


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
