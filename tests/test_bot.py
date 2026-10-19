from datetime import UTC, datetime

from bot import texts
from bot.keyboards import (
    PlaceChoice,
    RenameChoice,
    ReplaceChoice,
    place_keyboard,
    rename_keyboard,
    replace_keyboard,
)
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
    assert "1. «Внески» — Кабан" in text and f"2. «Внески на зиму» — {texts.ARCHIVE}" in text


def test_every_rejection_reason_has_a_message():
    assert set(texts.EXTRACTION_ERRORS) == set(FailureReason)
