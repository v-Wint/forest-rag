"""Questions: text → the place it is about (if not named, the animal picks it with buttons)
→ the answer with its sources. Every reply is a reply to the question, so place buttons
find their question even after the bot restarted."""

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.keyboards import QuestionPlace, question_place_keyboard
from forest_bot.application.answer import answer_question, find_place
from forest_bot.domain.forest_map import UnknownPlace
from forest_bot.settings import settings

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text.as_("question"))
async def on_question(message: Message, question: str) -> None:
    if len(question) > settings.max_question_chars:
        await message.reply(texts.QUESTION_TOO_LONG.format(max=settings.max_question_chars))
        return
    reply = await message.reply(texts.THINKING)
    try:
        place = await find_place(question)
    except Exception:
        logger.exception("finding the place of a question failed")
        await reply.edit_text(texts.ERROR)
        return
    if place is None:
        await reply.edit_text(texts.ASK_QUESTION_PLACE, reply_markup=question_place_keyboard())
        return
    await _answer(reply, question, place.id)


@router.callback_query(
    QuestionPlace.filter(),
    F.message.as_("buttons"),
    F.message.reply_to_message.text.as_("question"),
)
async def on_question_place(
    callback: CallbackQuery, callback_data: QuestionPlace, buttons: Message, question: str
) -> None:
    await callback.answer()
    try:
        await buttons.edit_text(texts.THINKING)  # also removes the buttons
    except TelegramBadRequest:  # "message is not modified": pressed twice, the first answers
        return
    await _answer(buttons, question, callback_data.place_id)


@router.callback_query(QuestionPlace.filter())
async def on_lost_question(callback: CallbackQuery) -> None:
    # The question was deleted, or the buttons are older than 48 hours: Telegram no longer
    # shows the bot that message, nor what it replies to.
    await callback.answer(texts.QUESTION_LOST, show_alert=True)


async def _answer(reply: Message, question: str, place_id: str) -> None:
    """Turn the bot's reply to the question into the answer."""
    try:
        answer = await answer_question(question, place_id)
    except UnknownPlace:  # the map changed since the buttons were sent
        await reply.edit_text(texts.UNKNOWN_PLACE)
        return
    except Exception:
        logger.exception("answering a question at %s failed", place_id)
        await reply.edit_text(texts.ERROR)
        return
    first, *rest = texts.answer_messages(answer)
    await reply.edit_text(first)
    for piece in rest:
        await reply.answer(piece)
