"""The Telegram bot, by long polling: no public address needed.

uv run python -m bot
"""

import asyncio

from aiogram import Bot, Dispatcher

from bot import questions, start, upload
from forest_bot.application.startup import running, setup_logging
from forest_bot.settings import settings


async def main() -> None:
    if settings.telegram_bot_token is None:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    async with running():
        bot = Bot(settings.telegram_bot_token.get_secret_value())
        dispatcher = Dispatcher()
        # Order matters: a name typed during registration must not be taken for a question.
        dispatcher.include_routers(start.router, upload.router, questions.router)
        await dispatcher.start_polling(bot)  # closes the bot's HTTP session when it stops


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())
