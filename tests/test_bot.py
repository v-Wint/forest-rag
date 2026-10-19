from datetime import UTC, datetime

from bot import texts
from bot.keyboards import (
    PlaceChoice,
    QuestionPlace,
    RenameChoice,
    ReplaceChoice,
    place_keyboard,
    question_place_keyboard,
    rename_keyboard,
    replace_keyboard,
)
from forest_bot.application.answer import Answer
from forest_bot.application.ingest import FailureReason
from forest_bot.domain import CurrentDocument
from forest_bot.domain.forest_map import forest_map

# Telegram rejects callback data longer than 64 bytes.
MAX_CALLBACK_BYTES = 64


def _choices(markup) -> list[PlaceChoice]:
    return [PlaceChoice.unpack(b.callback_data) for row in markup.inline_keyboard for b in row]


def test_suggested_place_is_alone_on_top_then_every_other_place():
    suggested = forest_map.places["under_willow"]
    markup = place_keyboard(12, suggested)

    rows = markup.inline_keyboard
    assert len(rows[0]) == 1 and rows[0][0].text.startswith("✅")
    assert all(len(row) <= 2 for row in rows[1:])
    choices = _choices(markup)
    assert choices[0].place_id == "under_willow"
    assert sorted(c.place_id for c in choices) == sorted(forest_map.places)
    assert {c.document_id for c in choices} == {12}


def test_without_a_suggestion_every_place_two_per_row():
    markup = place_keyboard(12, None)
    assert [len(row) for row in markup.inline_keyboard] == [2] * 6
    assert not any(b.text.startswith("✅") for row in markup.inline_keyboard for b in row)


def test_button_data_fits_telegram_for_every_place():
    big = 2**31 - 1  # documents.id is a 32-bit integer
    for place_id in forest_map.places:
        for data in (
            PlaceChoice(document_id=big, place_id=place_id).pack(),
            ReplaceChoice(document_id=big, place_id=place_id, replaces_id=big).pack(),
            RenameChoice(document_id=big, rename=False).pack(),
            QuestionPlace(place_id=place_id).pack(),
        ):
            assert len(data.encode()) <= MAX_CALLBACK_BYTES, data


def _current(id: int, title: str, author_name: str | None) -> CurrentDocument:
    when = datetime(2026, 9, 12, tzinfo=UTC)
    place = forest_map.places["under_oak"]
    return CurrentDocument(id, title, place, author_name, when, f"{title}.pdf")


def test_rename_buttons_show_both_file_names_the_new_one_first():
    markup = rename_keyboard(12, "Внески 2026.pdf", "Членські внески.pdf")
    buttons = [b for row in markup.inline_keyboard for b in row]
    assert [b.text for b in buttons] == ["🆕 Внески 2026.pdf", "📄 Членські внески.pdf"]
    choices = [RenameChoice.unpack(b.callback_data or "") for b in buttons]
    assert [(c.document_id, c.rename) for c in choices] == [(12, True), (12, False)]


def test_one_earlier_version_is_a_yes_or_no_question():
    earlier = [_current(7, "Членські внески", "Кабан")]
    choices = [
        ReplaceChoice.unpack(b.callback_data or "")
        for row in replace_keyboard(12, "under_oak", earlier).inline_keyboard
        for b in row
    ]
    assert [c.replaces_id for c in choices] == [7, 0]
    text = texts.ask_replace(forest_map.places["under_oak"], earlier)
    assert "«Членські внески» — Кабан, 12.09.2026" in text


def test_several_earlier_versions_are_numbered_like_their_buttons():
    earlier = [_current(7, "Внески", "Кабан"), _current(8, "Внески на зиму", None)]
    markup = replace_keyboard(12, "under_oak", earlier)
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert labels == ["🔁 Замінює 1", "🔁 Замінює 2", texts.SEPARATE_BUTTON]
    text = texts.ask_replace(forest_map.places["under_oak"], earlier)
    assert "1. «Внески» — Кабан, 12.09.2026\n" in text
    assert f"2. «Внески на зиму» — {texts.ARCHIVE}\n" in text  # the archive has no date


def test_every_rejection_reason_has_a_message():
    assert set(texts.EXTRACTION_ERRORS) == set(FailureReason)


def test_a_question_can_be_asked_about_every_place():
    markup = question_place_keyboard()
    buttons = [b for row in markup.inline_keyboard for b in row]
    choices = [QuestionPlace.unpack(b.callback_data or "") for b in buttons]
    assert [c.place_id for c in choices] == list(forest_map.places)


def test_an_answer_lists_its_sources_numbered_like_its_marks():
    sources = [_current(7, "Членські внески", None), _current(8, "Внески на зиму", "Кабан")]
    answer = Answer(forest_map.places["under_oak"], "4 жолуді [1], взимку 5 [2].", sources)
    assert texts.answer_messages(answer) == [
        "4 жолуді [1], взимку 5 [2].\n\n"
        "Джерела:\n"
        f"[1] «Членські внески», 🧤 Під дубом — {texts.ARCHIVE}\n"
        "[2] «Внески на зиму», 🧤 Під дубом — Кабан, 12.09.2026"
    ]


def test_no_answer_names_the_place_searched():
    answer = Answer(forest_map.places["under_oak"], None, [])
    assert texts.answer_messages(answer) == [texts.NO_ANSWER.format(place="Під дубом")]


def test_a_long_answer_is_split_at_line_breaks():
    sources = [_current(n, f"Порада {n}", "Кабан") for n in range(1, 101)]
    answer = Answer(forest_map.places["under_oak"], "Жолуді. " * 400, sources)
    messages = texts.answer_messages(answer)
    assert len(messages) > 1
    assert all(len(m) <= texts.MAX_MESSAGE_CHARS for m in messages)
    assert messages[-1].endswith("[100] «Порада 100», 🧤 Під дубом — Кабан, 12.09.2026")
    assert all(m.split("\n")[0].startswith(("Жолуді", "[")) for m in messages[1:])


def test_a_line_longer_than_a_message_is_cut_inside():
    assert texts.split_message("ab\ncdefg\nh", limit=3) == ["ab", "cde", "fg", "h"]
