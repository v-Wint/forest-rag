"""One file through the whole ETL. The bot calls this once per upload; the archive
script calls it once per file in a folder."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from forest_bot.application.etl.extractors import extract
from forest_bot.application.etl.load import SaveResult, save_document
from forest_bot.application.etl.transform import transform
from forest_bot.domain import ParsedDocument


def parse_file(data: bytes, filename: str) -> ParsedDocument:
    """Extract + transform. Synchronous and CPU-bound (PDF rendering, OCR)."""
    return transform(extract(data), filename)


async def ingest_document(
    session: AsyncSession, data: bytes, filename: str, *, author_id: int | None = None
) -> SaveResult:
    """Parse one file and store it as `pending`. The caller owns the transaction."""
    # A scan takes seconds to OCR: run it off the event loop so the bot keeps answering.
    parsed = await asyncio.to_thread(parse_file, data, filename)
    return await save_document(session, parsed, author_id=author_id)
