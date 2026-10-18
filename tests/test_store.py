"""store.py against the real PostgreSQL (see the run_in_db fixture)."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from forest_bot.application.ingest import store
from forest_bot.domain import DocStatus, ParsedDocument
from forest_bot.domain.enums import ExtractionMethod, FileKind
from forest_bot.domain.forest_map import forest_map
from forest_bot.infrastructure import db

DOCUMENT = ParsedDocument(
    source_filename="test.txt",
    file_kind=FileKind.TXT,
    extraction_method=ExtractionMethod.PLAIN_TEXT,
    title="Тест",
    text="Внесок — 4 жолуді.",
    content_hash=uuid.uuid4().hex,
)
OAK = forest_map.place("under_oak")


async def _lifecycle() -> dict:
    seen = {}
    async with db.sessions() as session:
        first = await store.save_draft(session, DOCUMENT, author_id=None)
        second = await store.save_draft(session, DOCUMENT, author_id=None)
        seen["drafts"] = (first.id, second.id, first.status, second.status)
        seen["current_before"] = await store.find_active_with_same_text(
            session, DOCUMENT.content_hash
        )
        seen["ever_active_before"] = await store.was_ever_active(session, DOCUMENT.content_hash)

        seen["activated"] = await store.activate_if_draft(session, first.id, OAK)
        seen["activated_twice"] = await store.activate_if_draft(session, first.id, OAK)
        # The same text can be current only once.
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await store.activate_if_draft(session, second.id, OAK)
        current = await store.find_active_with_same_text(session, DOCUMENT.content_hash)
        seen["current"] = current.id if current else None
        seen["at_oak"] = [d.id for d in await store.list_active_at(session, "under_oak")]

        seen["supersede_elsewhere"] = await store.supersede_if_active_at(
            session, first.id, "in_hazel"
        )
        replaced = await store.supersede_if_active_at(session, first.id, "under_oak")
        seen["replaced"] = replaced.status if replaced else None
        seen["supersede_twice"] = await store.supersede_if_active_at(session, first.id, "under_oak")
        seen["ever_active_after"] = await store.was_ever_active(session, DOCUMENT.content_hash)
    return seen


def test_draft_activate_supersede(run_in_db):
    seen = run_in_db(_lifecycle)

    first_id, second_id, *statuses = seen["drafts"]
    assert first_id != second_id  # a draft never blocks another one
    assert statuses == [DocStatus.PENDING, DocStatus.PENDING]
    assert seen["current_before"] is None and not seen["ever_active_before"]

    assert seen["activated"] and not seen["activated_twice"]
    assert seen["current"] == first_id
    assert first_id in seen["at_oak"]

    assert seen["supersede_elsewhere"] is None  # only at its own place
    assert seen["replaced"] == DocStatus.SUPERSEDED
    assert seen["supersede_twice"] is None
    assert seen["ever_active_after"]  # replaced counts too
