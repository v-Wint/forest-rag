"""Questions in plain text. Answering is not built yet."""

from aiogram import F, Router
from aiogram.types import Message

from bot import texts

router = Router()


@router.message(F.text)
async def on_question(message: Message) -> None:
    await message.answer(texts.QUESTIONS_SOON)
