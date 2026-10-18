"""Adding a document: file → (first time: the animal's name) → place → (it looks like a new
version of a current document: replace it?) → used in answers."""

import asyncio
import io
import logging
from collections import defaultdict
from contextlib import suppress

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Document, InlineKeyboardMarkup, Message

from bot import texts
from bot.keyboards import (
    PlaceChoice,
    RenameChoice,
    ReplaceChoice,
    place_keyboard,
    rename_keyboard,
    replace_keyboard,
)
from forest_bot.application.ingest import (
    AlreadyCurrent,
    AlreadyHandled,
    DocumentsChanged,
    ExtractionError,
    FailureReason,
    NotTheAuthor,
    activate,
    find_earlier_versions,
    rename_current,
    upload_document,
)
from forest_bot.application.users import InvalidName, get_user, register_user
from forest_bot.domain.forest_map import UnknownPlace, forest_map
from forest_bot.settings import settings

logger = logging.getLogger(__name__)
router = Router()

# One animal's files are handled one at a time, in the order sent. Telegram delivers files
# sent together as separate updates at once; without this they would race for the
# registration and overwrite each other in the state data.
_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

# What to say when activating is refused because the documents changed meanwhile.
_REFUSALS = {
    AlreadyCurrent: texts.ALREADY_ADDED,
    DocumentsChanged: texts.DOCUMENTS_CHANGED,
    UnknownPlace: texts.UNKNOWN_PLACE,
}


class Registration(StatesGroup):
    # Waiting for the real name; the files sent meanwhile are kept in the state data.
    name = State()


@router.message(F.document.as_("document"), F.from_user.id.as_("user_id"))
async def on_document(
    message: Message, document: Document, user_id: int, state: FSMContext, bot: Bot
) -> None:
    async with _locks[user_id]:
        if await get_user(user_id) is not None:
            await _upload(message, bot, document, author_id=user_id)
            return
        queued = (await state.get_data()).get("documents", [])
        await state.update_data(documents=[*queued, document.model_dump()])
        if queued:
            await message.answer(texts.QUEUED)
        else:
            await state.set_state(Registration.name)
            await message.answer(texts.ASK_NAME)


@router.message(Registration.name, F.text.as_("name"), F.from_user.id.as_("user_id"))
async def on_name(message: Message, name: str, user_id: int, state: FSMContext, bot: Bot) -> None:
    async with _locks[user_id]:
        try:
            user = await register_user(user_id, name)
        except InvalidName:
            await message.answer(texts.BAD_NAME.format(max=settings.max_name_chars))
            return
        queued = (await state.get_data()).get("documents", [])
        await state.clear()
        await message.answer(texts.REGISTERED.format(name=user.real_name))
        for data in queued:
            await _upload(message, bot, Document.model_validate(data), author_id=user_id)


@router.message(F.photo)
async def on_photo(message: Message) -> None:
    await message.answer(texts.SEND_AS_FILE)


@router.callback_query(PlaceChoice.filter())
async def on_place(callback: CallbackQuery, callback_data: PlaceChoice, bot: Bot) -> None:
    document_id, place_id = callback_data.document_id, callback_data.place_id
    try:
        earlier = await find_earlier_versions(
            document_id, place_id, author_id=callback.from_user.id
        )
    except AlreadyHandled:  # the button was pressed twice: the first press answers
        await callback.answer()
        return
    except NotTheAuthor:  # the buttons stay for their author
        await callback.answer(texts.NOT_YOURS, show_alert=True)
        return
    except UnknownPlace:  # the map changed since the buttons were sent
        await callback.answer(texts.UNKNOWN_PLACE, show_alert=True)
        return
    except Exception:
        logger.exception("looking for earlier versions of %s failed", callback_data)
        await callback.answer(texts.ERROR, show_alert=True)
        return
    if not earlier:
        await _activate(callback, bot, document_id, place_id, replaces_id=None)
        return
    await callback.answer()
    await _answered(
        callback,
        bot,
        texts.ask_replace(forest_map.place(place_id), earlier),
        reply_markup=replace_keyboard(document_id, place_id, earlier),
    )


@router.callback_query(ReplaceChoice.filter())
async def on_replace(callback: CallbackQuery, callback_data: ReplaceChoice, bot: Bot) -> None:
    await _activate(
        callback,
        bot,
        callback_data.document_id,
        callback_data.place_id,
        replaces_id=callback_data.replaces_id or None,
    )


@router.callback_query(RenameChoice.filter())
async def on_rename(callback: CallbackQuery, callback_data: RenameChoice, bot: Bot) -> None:
    text = texts.NAME_KEPT
    if callback_data.rename:
        try:
            current = await rename_current(
                callback_data.document_id, author_id=callback.from_user.id
            )
        except NotTheAuthor:
            await callback.answer(texts.NOT_YOURS, show_alert=True)
            return
        except DocumentsChanged:
            text = texts.RENAME_STALE
        except Exception:
            logger.exception("renaming for %s failed", callback_data)
            text = texts.ERROR
        else:
            text = texts.RENAMED.format(title=current.title, filename=current.filename)
    await callback.answer()
    await _answered(callback, bot, text)


async def _upload(message: Message, bot: Bot, document: Document, *, author_id: int) -> None:
    # Telegram does not let bots download more than 20 MB: say so before trying.
    if document.file_size and document.file_size > settings.max_file_bytes:
        await message.answer(texts.EXTRACTION_ERRORS[FailureReason.TOO_LARGE])
        return
    filename = document.file_name or "document"
    status = await message.answer(texts.READING.format(filename=filename))
    try:
        data = io.BytesIO()
        await bot.download(document, destination=data)
        upload = await upload_document(data.getvalue(), filename, author_id=author_id)
    except ExtractionError as exc:
        logger.info("rejected %s: %s", filename, exc)
        await status.edit_text(texts.EXTRACTION_ERRORS[exc.reason])
        return
    except Exception:  # Telegram, the database or the LLM: log it, tell the animal
        logger.exception("upload of %s failed", filename)
        await status.edit_text(texts.ERROR)
        return

    if upload.exact_copy_of is not None:
        current = upload.exact_copy_of
        names = dict(title=current.title, place=current.place.name)
        if current.filename == filename:
            await status.edit_text(texts.ALREADY_CURRENT.format(**names))
        else:
            await status.edit_text(
                texts.ASK_RENAME.format(**names),
                reply_markup=rename_keyboard(upload.document_id, filename, current.filename),
            )
        return
    if upload.suggested_place is None:
        text = texts.ASK_PLACE_UNCLEAR.format(title=upload.title)
    else:
        text = texts.ASK_PLACE.format(title=upload.title, place=upload.suggested_place.name)
    await status.edit_text(
        text, reply_markup=place_keyboard(upload.document_id, upload.suggested_place)
    )


async def _activate(
    callback: CallbackQuery, bot: Bot, document_id: int, place_id: str, *, replaces_id: int | None
) -> None:
    """Make the document current; a long guide takes seconds to embed."""
    await callback.answer(texts.ADDING)
    message = callback.message if isinstance(callback.message, Message) else None
    try:
        activated = await activate(
            document_id, place_id, replaces_id=replaces_id, author_id=callback.from_user.id
        )
    except AlreadyHandled:  # the button was pressed twice: the first press answers
        return
    except NotTheAuthor:  # the buttons stay for their author
        if message:
            await message.answer(texts.NOT_YOURS)
        return
    except (AlreadyCurrent, DocumentsChanged, UnknownPlace) as exc:
        logger.info("activating #%d refused: %r", document_id, exc)
        text = _REFUSALS[type(exc)].format(place=_place_name(place_id))
    except Exception:
        logger.exception("activating #%d at %s failed", document_id, place_id)
        text = texts.ERROR
    else:
        old, place = activated.replaced_title, activated.place.name
        if old is None:
            text = texts.PLACED.format(title=activated.title, place=place)
        else:
            text = texts.REPLACED.format(title=activated.title, old=old, place=place)
            author_id = activated.replaced_author_id
            if author_id is not None and author_id != callback.from_user.id:
                notice = texts.YOURS_REPLACED.format(old=old, place=place, title=activated.title)
                await _tell(bot, author_id, notice)
    await _answered(callback, bot, text)


async def _answered(
    callback: CallbackQuery, bot: Bot, text: str, reply_markup: InlineKeyboardMarkup | None = None
) -> None:
    """The question under the pressed button is answered: say what happened (or ask the next
    question), then delete the question so only the outcome stays in the chat."""
    question = callback.message
    chat_id = question.chat.id if question else callback.from_user.id
    await bot.send_message(chat_id, text, reply_markup=reply_markup)
    if question is None:
        return
    try:
        await bot.delete_message(chat_id, question.message_id)
    except TelegramBadRequest:
        # Bots may delete their messages for 48 hours only: then just drop the buttons
        # (already gone if something removed them meanwhile).
        with suppress(TelegramBadRequest):
            await bot.edit_message_reply_markup(
                chat_id=chat_id, message_id=question.message_id, reply_markup=None
            )


def _place_name(place_id: str) -> str:
    place = forest_map.places.get(place_id)
    return place.name if place else place_id


async def _tell(bot: Bot, user_id: int, text: str) -> None:
    try:
        await bot.send_message(user_id, text)
    except TelegramAPIError:  # e.g. they blocked the bot: the replacement stands anyway
        logger.warning("could not tell %d that their document was replaced", user_id)
