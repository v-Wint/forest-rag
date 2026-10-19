"""Buttons. Each button carries everything its answer needs (the document, the place, the
version it replaces), so pressing it works even after the bot restarted: the draft is in
the database."""

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import texts
from forest_bot.domain import CurrentDocument
from forest_bot.domain.forest_map import Place, forest_map


class PlaceChoice(CallbackData, prefix="place"):
    document_id: int
    place_id: str


class RenameChoice(CallbackData, prefix="rename"):
    # The draft keeps the new file name: it does not fit in the 64 bytes of a button.
    document_id: int
    rename: bool


class ReplaceChoice(CallbackData, prefix="replace"):
    document_id: int
    place_id: str
    replaces_id: int  # 0: a separate document, it replaces nothing


def place_keyboard(document_id: int, suggested: Place | None) -> InlineKeyboardMarkup:
    """The suggested place alone on top, then every other place two per row:
    the whole forest, the parts, the mittens."""
    builder = InlineKeyboardBuilder()
    places = list(forest_map.places.values())
    if suggested is not None:
        places = [suggested] + [p for p in places if p != suggested]
    for place in places:
        label = texts.place_label(place)
        if place == suggested:
            label = f"✅ {label}"
        builder.button(
            text=label, callback_data=PlaceChoice(document_id=document_id, place_id=place.id)
        )
    # The last size repeats for the remaining rows.
    builder.adjust(*([1] if suggested else []), 2)
    return builder.as_markup()


def rename_keyboard(document_id: int, new_name: str, old_name: str) -> InlineKeyboardMarkup:
    """Both file names, the new one first."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"🆕 {new_name}", callback_data=RenameChoice(document_id=document_id, rename=True)
    )
    builder.button(
        text=f"📄 {old_name}", callback_data=RenameChoice(document_id=document_id, rename=False)
    )
    builder.adjust(1)
    return builder.as_markup()


def replace_keyboard(
    document_id: int, place_id: str, earlier: list[CurrentDocument]
) -> InlineKeyboardMarkup:
    """One button per earlier version (numbered as in texts.ask_replace), then "separate"."""
    builder = InlineKeyboardBuilder()
    for n, document in enumerate(earlier, start=1):
        label = texts.REPLACE_ONE_BUTTON if len(earlier) == 1 else texts.REPLACE_NTH_BUTTON
        builder.button(
            text=label.format(n=n),
            callback_data=ReplaceChoice(
                document_id=document_id, place_id=place_id, replaces_id=document.id
            ),
        )
    builder.button(
        text=texts.SEPARATE_BUTTON,
        callback_data=ReplaceChoice(document_id=document_id, place_id=place_id, replaces_id=0),
    )
    builder.adjust(1)
    return builder.as_markup()
