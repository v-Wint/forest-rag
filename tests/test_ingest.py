"""ingest.py's decisions. The database (see the fake_db fixture), its queries in store.py,
the embedding model and the LLM are replaced with fixed results."""

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from forest_bot.application.ingest import (
    AlreadyCurrent,
    AlreadyHandled,
    DocumentsChanged,
    NotTheAuthor,
    activate,
    find_earlier_versions,
    ingest,
    rename_current,
    seed_document,
    store,
    upload_document,
)
from forest_bot.application.ingest.ingest import parse_file
from forest_bot.domain import Chunk, DocStatus, Document
from forest_bot.domain.forest_map import forest_map

DUES = (
    "Членські внески\n\nКожен дорослий звір здає 4 жолуді на місяць до 10 числа. Внески "
    "приймає скарбник у кошик біля входу."
)
SQUIRREL, BOAR = 1, 2
OAK = forest_map.place("under_oak")


def _document(
    id: int, filename: str, *, status=DocStatus.PENDING, author_id: int | None = SQUIRREL
) -> Document:
    parsed = parse_file(DUES.encode(), filename)
    placed = status != DocStatus.PENDING
    return Document(
        id=id,
        title=parsed.title,
        status=status,
        scope_level=OAK.level if placed else None,
        scope_id=OAK.id if placed else None,
        author_id=author_id,
        uploaded_at=datetime(2026, 9, 12, tzinfo=UTC),
        source_filename=filename,
        file_kind=parsed.file_kind,
        extraction_method=parsed.extraction_method,
        content_hash=parsed.content_hash,
        full_text=parsed.text,
    )


def _returning(value):
    async def call(*args, **kwargs):
        return value

    return call


def _raising(error: Exception):
    async def call(*args, **kwargs):
        raise error

    return call


_must_not_be_called = _raising(AssertionError("must not be called"))


def test_same_text_in_another_format_has_the_same_hash(make_docx):
    as_txt = parse_file(DUES.encode(), "a.txt")
    as_docx = parse_file(make_docx(*DUES.split("\n")), "b.docx")
    assert as_txt.content_hash == as_docx.content_hash


def test_an_exact_copy_points_to_the_current_document(fake_db, monkeypatch):
    monkeypatch.setattr(store, "save_draft", _returning(_document(2, "Членські внески.txt")))
    current = _document(1, "Внески.txt", status=DocStatus.ACTIVE, author_id=BOAR)
    monkeypatch.setattr(store, "find_active_with_same_text", _returning(current))
    monkeypatch.setattr(ingest, "suggest_place", _must_not_be_called)

    upload = asyncio.run(upload_document(DUES.encode(), "Членські внески.txt", author_id=SQUIRREL))

    assert upload.document_id == 2 and upload.suggested_place is None
    assert upload.exact_copy_of is not None
    assert (upload.exact_copy_of.id, upload.exact_copy_of.filename) == (1, "Внески.txt")


def test_without_the_llm_the_author_picks_the_place(fake_db, monkeypatch):
    monkeypatch.setattr(store, "save_draft", _returning(_document(2, "Внески.txt")))
    monkeypatch.setattr(store, "find_active_with_same_text", _returning(None))
    monkeypatch.setattr(ingest, "suggest_place", _raising(RuntimeError("Groq is down")))

    upload = asyncio.run(upload_document(DUES.encode(), "Внески.txt", author_id=SQUIRREL))

    assert upload.exact_copy_of is None and upload.suggested_place is None


@pytest.mark.parametrize(
    ("status", "author_id", "error"),
    [
        (DocStatus.PENDING, BOAR, NotTheAuthor),  # someone else's buttons
        (DocStatus.ACTIVE, SQUIRREL, AlreadyHandled),  # a button pressed twice
    ],
)
def test_only_the_author_decides_and_only_once(fake_db, status, author_id, error):
    fake_db.documents[2] = _document(2, "Внески.txt", status=status)
    with pytest.raises(error):
        asyncio.run(find_earlier_versions(2, "under_oak", author_id=author_id))
    with pytest.raises(error):
        asyncio.run(activate(2, "under_oak", author_id=author_id))
    with pytest.raises(error):
        asyncio.run(rename_current(2, author_id=author_id))


def test_renaming_gives_the_current_document_the_new_file_name(fake_db, monkeypatch):
    fake_db.documents[2] = _document(2, "Внески 2026.txt")
    current = _document(1, "Внески.txt", status=DocStatus.ACTIVE, author_id=BOAR)
    monkeypatch.setattr(store, "find_active_with_same_text", _returning(current))

    renamed = asyncio.run(rename_current(2, author_id=SQUIRREL))

    assert (renamed.id, renamed.title, renamed.filename) == (1, "Внески 2026", "Внески 2026.txt")


def test_renaming_a_text_replaced_meanwhile_is_refused(fake_db, monkeypatch):
    fake_db.documents[2] = _document(2, "Внески 2026.txt")
    monkeypatch.setattr(store, "find_active_with_same_text", _returning(None))
    with pytest.raises(DocumentsChanged):
        asyncio.run(rename_current(2, author_id=SQUIRREL))


@pytest.fixture
def new_version(fake_db, monkeypatch) -> int:
    """A draft by the squirrel, ready to embed."""
    fake_db.documents[2] = _document(2, "Внески (нові).txt")
    monkeypatch.setattr(ingest, "embed_document", _returning([Chunk(ordinal=0, text=DUES)]))
    return 2


def test_a_new_version_replaces_the_old_one_with_its_chunks(fake_db, new_version, monkeypatch):
    old = _document(1, "Внески.txt", status=DocStatus.SUPERSEDED, author_id=BOAR)
    monkeypatch.setattr(store, "supersede_if_active_at", _returning(old))
    monkeypatch.setattr(store, "activate_if_draft", _returning(True))

    activated = asyncio.run(activate(new_version, "under_oak", replaces_id=1, author_id=SQUIRREL))

    assert (activated.title, activated.place) == ("Внески (нові)", OAK)
    assert (activated.replaced_title, activated.replaced_author_id) == ("Внески", BOAR)
    assert [c.text for c in fake_db.added] == [DUES]  # type: ignore[attr-defined]


def test_replacing_a_version_replaced_meanwhile_is_refused(fake_db, new_version, monkeypatch):
    monkeypatch.setattr(store, "supersede_if_active_at", _returning(None))
    with pytest.raises(DocumentsChanged):
        asyncio.run(activate(new_version, "under_oak", replaces_id=1, author_id=SQUIRREL))
    assert fake_db.added == []


def test_the_same_text_made_current_meanwhile_is_refused(fake_db, new_version, monkeypatch):
    unique_index = IntegrityError("UPDATE documents", {}, Exception("uq_documents_current"))
    monkeypatch.setattr(store, "activate_if_draft", _raising(unique_index))
    with pytest.raises(AlreadyCurrent):
        asyncio.run(activate(new_version, "under_oak", author_id=SQUIRREL))


def test_archive_seeding_skips_files_seeded_before_without_reading_them(fake_db, monkeypatch):
    monkeypatch.setattr(store, "archive_file_loaded", _returning(True))
    monkeypatch.setattr(ingest, "parse_file", _must_not_be_called)
    monkeypatch.setattr(store, "save_draft", _must_not_be_called)

    seeded = asyncio.run(seed_document(DUES.encode(), "Членські_внески.txt"))

    assert seeded.already_loaded and seeded.title == "Членські внески"


def test_archive_seeding_skips_texts_seen_before(fake_db, monkeypatch):
    monkeypatch.setattr(store, "archive_file_loaded", _returning(False))
    monkeypatch.setattr(store, "was_ever_active", _returning(True))
    monkeypatch.setattr(store, "save_draft", _must_not_be_called)
    monkeypatch.setattr(ingest, "suggest_place", _must_not_be_called)

    seeded = asyncio.run(seed_document(DUES.encode(), "Внески.txt"))

    assert seeded.already_loaded and seeded.place is None
