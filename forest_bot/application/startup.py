"""What every program (the bot, the pipeline) does around its work:

setup_logging()
async with running():
    ...
"""

import asyncio
import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from forest_bot.application.ingest.extractors import ocr
from forest_bot.infrastructure import db
from forest_bot.infrastructure.embedder import embedder
from forest_bot.infrastructure.llm import get_llm
from forest_bot.settings import settings


def setup_logging() -> None:
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    # Cyrillic file names in the log: the Windows console is not UTF-8 by default.
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]


@asynccontextmanager
async def running() -> AsyncGenerator[None]:
    """Startup checks, then the program's work, then close the database connections.

    The checks fail at startup rather than on the first upload: Tesseract and its language
    data, the Groq key. The embedding model is loaded now (seconds) instead of on first use.
    """
    ocr.check_available()
    get_llm()
    await asyncio.to_thread(embedder.load)
    try:
        yield
    finally:
        await db.engine.dispose()
