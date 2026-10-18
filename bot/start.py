from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot import texts

router = Router()


@router.message(CommandStart())
@router.message(Command("help"))
async def on_start(message: Message, state: FSMContext) -> None:
    await state.clear()  # e.g. abandons waiting for a name
    await message.answer(texts.START)
