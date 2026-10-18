import asyncio
import io
from collections.abc import Awaitable, Callable

import docx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from forest_bot.infrastructure import db


@pytest.fixture
def make_docx() -> Callable[..., bytes]:
    def make(*paragraphs: str) -> bytes:
        document = docx.Document()
        for paragraph in paragraphs:
            document.add_paragraph(paragraph)
        buffer = io.BytesIO()
        document.save(buffer)
        return buffer.getvalue()

    return make


@pytest.fixture
def run_in_db(monkeypatch) -> Callable[[Callable[[], Awaitable]], object]:
    """Run an async test body against the real PostgreSQL inside one transaction that is
    rolled back, so the database is left untouched. Each `db.sessions.begin()` in the code
    under test commits only a savepoint. Skips the test when no database is reachable."""

    async def in_transaction(body: Callable[[], Awaitable]) -> object:
        try:
            async with db.engine.connect() as connection:
                transaction = await connection.begin()
                sessions = async_sessionmaker(
                    bind=connection,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                )
                monkeypatch.setattr(db, "sessions", sessions)
                try:
                    return await body()
                finally:
                    await transaction.rollback()
        finally:
            await db.engine.dispose()  # its connections belong to this event loop

    def run(body: Callable[[], Awaitable]) -> object:
        try:
            return asyncio.run(in_transaction(body))
        except OSError as exc:  # connection refused
            pytest.skip(f"no database: {type(exc).__name__}")

    return run
