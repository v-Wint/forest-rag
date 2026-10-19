import io
from collections.abc import Callable
from contextlib import asynccontextmanager

import docx
import pytest

from forest_bot.domain import Document
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


class FakeSession:
    """Stands in for an AsyncSession: documents looked up by id, and what was added."""

    def __init__(self) -> None:
        self.documents: dict[int, Document] = {}
        self.added: list[object] = []

    async def get_one(self, model: type, id: int) -> Document:
        return self.documents[id]

    def add_all(self, objects: list[object]) -> None:
        self.added.extend(objects)


class _Sessions:
    def __init__(self, session: FakeSession) -> None:
        self._session = session

    def __call__(self):
        return self._open()

    def begin(self):
        return self._open()

    @asynccontextmanager
    async def _open(self):
        yield self._session


@pytest.fixture
def fake_db(monkeypatch) -> FakeSession:
    """No database: db.sessions() and db.sessions.begin() open this one fake session. Each
    test replaces the queries it needs (store.py, search.py) with fixed results."""
    session = FakeSession()
    monkeypatch.setattr(db, "sessions", _Sessions(session))
    return session
