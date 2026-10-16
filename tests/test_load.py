"""save_document against the real PostgreSQL. Everything runs in a transaction that is
rolled back, so the database is left untouched. Skipped when no database is reachable."""

import asyncio
import uuid

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from forest_bot.application.etl import save_document
from forest_bot.domain import ParsedDocument
from forest_bot.domain.enums import ExtractionMethod, FileKind
from forest_bot.infrastructure.db import engine

DOCUMENT = ParsedDocument(
    source_filename="test.txt",
    file_kind=FileKind.TXT,
    extraction_method=ExtractionMethod.PLAIN_TEXT,
    title="Тест",
    text="Внесок — 4 жолуді.",
    content_hash=uuid.uuid4().hex,
)


async def _save_twice() -> tuple:
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            session = AsyncSession(bind=connection)
            first = await save_document(session, DOCUMENT)
            second = await save_document(session, DOCUMENT)
            await transaction.rollback()
    finally:
        await engine.dispose()
    return first, second


def test_save_is_idempotent_by_content_hash():
    try:
        first, second = asyncio.run(_save_twice())
    except (OperationalError, OSError) as exc:  # OSError: connection refused
        pytest.skip(f"no database: {type(exc).__name__}")
    assert first.created
    assert not second.created
    assert second.document_id == first.document_id
