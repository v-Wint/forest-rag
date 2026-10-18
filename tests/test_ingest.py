"""ingest.py: reading a file offline, then the upload conversation end to end against the
real PostgreSQL (see the run_in_db fixture) and embedding model, with the LLM replaced."""

import uuid

import pytest
from sqlalchemy import func, select

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
    upload_document,
)
from forest_bot.application.ingest.ingest import parse_file
from forest_bot.application.users import register_user
from forest_bot.domain import Chunk, DocStatus, Document, ScopeLevel
from forest_bot.domain.forest_map import UnknownPlace, forest_map
from forest_bot.infrastructure import db

# Unique, so it never collides with a document already in the database.
CODE = uuid.uuid4().hex
DUES = (
    "Членські внески\n\nКожен дорослий звір здає 4 жолуді на місяць до 10 числа. Внески "
    "приймає скарбник у кошик біля входу. Замість 4 жолудів можна віддати 2 лісові горіхи. "
    f"Код {CODE}."
)
NEW_DUES = DUES.replace("4 жолуді", "5 жолудів").replace("10 числа", "12 числа")
SQUIRREL, BOAR = 900_000_001, 900_000_002


def test_same_text_in_another_format_has_the_same_hash(make_docx):
    as_txt = parse_file(DUES.encode(), "a.txt")
    as_docx = parse_file(make_docx(*DUES.split("\n")), "b.docx")
    assert as_txt.content_hash == as_docx.content_hash


async def _fake_suggest(title: str, text: str):
    return forest_map.place("under_oak")


async def _upload(text: str, filename: str, author_id: int):
    return await upload_document(text.encode(), filename, author_id=author_id)


async def _conversation() -> dict:
    seen = {}
    await register_user(SQUIRREL, "Білка")
    await register_user(BOAR, "Кабан")

    first = await _upload(DUES, "Членські внески.txt", SQUIRREL)
    # Someone else's draft of the same text counts for nothing: it does not block this one.
    rival = await _upload(DUES, "внески.txt", BOAR)
    seen["first"], seen["rival"] = first, rival
    seen["placed"] = await activate(first.document_id, "under_oak", author_id=SQUIRREL)
    with pytest.raises(AlreadyHandled):  # the button pressed twice
        await activate(first.document_id, "under_oak", author_id=SQUIRREL)
    with pytest.raises(AlreadyHandled):  # a place button pressed again: not its own version
        await find_earlier_versions(first.document_id, "under_oak", author_id=SQUIRREL)
    with pytest.raises(AlreadyCurrent):  # the rival confirms too late
        await activate(rival.document_id, "under_oak", author_id=BOAR)
    # Current now: the same text again is that document; a new file name is only a draft
    # until its author says that document takes it.
    seen["same_name"] = await _upload(DUES, "Членські внески.txt", BOAR)
    copy = await _upload(DUES, "Внески 2026.txt", BOAR)
    seen["copy"] = copy
    with pytest.raises(NotTheAuthor):
        await rename_current(copy.document_id, author_id=SQUIRREL)
    seen["renamed"] = await rename_current(copy.document_id, author_id=BOAR)

    # A new version: found at its place, replaces the old one.
    new = await _upload(NEW_DUES, "Членські внески (нові).txt", BOAR)
    with pytest.raises(NotTheAuthor):
        await find_earlier_versions(new.document_id, "under_oak", author_id=SQUIRREL)
    seen["earlier"] = await find_earlier_versions(new.document_id, "under_oak", author_id=BOAR)
    seen["elsewhere"] = await find_earlier_versions(new.document_id, "in_hazel", author_id=BOAR)
    seen["replaced"] = await activate(
        new.document_id, "under_oak", replaces_id=first.document_id, author_id=BOAR
    )
    # Someone still deciding about the old version is too late as well.
    late = await _upload(NEW_DUES + " Оновлено.", "Внески.txt", SQUIRREL)
    with pytest.raises(DocumentsChanged):
        await activate(
            late.document_id, "under_oak", replaces_id=first.document_id, author_id=SQUIRREL
        )
    with pytest.raises(NotTheAuthor):
        await activate(late.document_id, "under_oak", author_id=BOAR)
    with pytest.raises(UnknownPlace):
        await activate(late.document_id, "under_birch", author_id=SQUIRREL)
    with pytest.raises(DocumentsChanged):  # renaming a text that was replaced meanwhile
        await rename_current(copy.document_id, author_id=BOAR)

    # The old version brought back: a new upload, which replaces the current one.
    back = await _upload(DUES, "Членські внески.txt", SQUIRREL)
    seen["back"] = back
    seen["back_earlier"] = await find_earlier_versions(
        back.document_id, "under_oak", author_id=SQUIRREL
    )
    await activate(back.document_id, "under_oak", replaces_id=new.document_id, author_id=SQUIRREL)

    async with db.sessions() as session:
        ids = {
            "first": first.document_id,
            "rival": rival.document_id,
            "new": new.document_id,
            "late": late.document_id,
            "back": back.document_id,
        }
        documents = {name: await session.get_one(Document, i) for name, i in ids.items()}
        seen["states"] = {name: d.status for name, d in documents.items()}
        seen["first_name"] = documents["first"].source_filename
        seen["back_scope"] = (documents["back"].scope_level, documents["back"].scope_id)
        seen["chunks"] = {
            name: await session.scalar(
                select(func.count()).select_from(Chunk).where(Chunk.document_id == i)
            )
            for name, i in ids.items()
        }
    seen["ids"] = ids
    return seen


def test_upload_replace_and_bring_back(run_in_db, monkeypatch):
    monkeypatch.setattr(ingest, "suggest_place", _fake_suggest)
    seen = run_in_db(_conversation)
    ids = seen["ids"]

    first = seen["first"]
    assert first.exact_copy_of is None and first.title == "Членські внески"
    assert first.suggested_place.id == "under_oak"
    assert seen["rival"].exact_copy_of is None and seen["rival"].document_id != ids["first"]
    assert seen["placed"].replaced_title is None

    same_name = seen["same_name"]
    assert (
        same_name.exact_copy_of is not None
        and same_name.exact_copy_of.filename == "Членські внески.txt"
    )
    copy = seen["copy"]
    assert copy.exact_copy_of is not None and copy.exact_copy_of.id == ids["first"]
    assert copy.exact_copy_of.author_name == "Білка" and copy.exact_copy_of.place.id == "under_oak"
    assert copy.exact_copy_of.filename == "Членські внески.txt"  # not renamed until asked
    assert copy.document_id != ids["first"]  # the draft that keeps the new name
    assert seen["renamed"].filename == seen["first_name"] == "Внески 2026.txt"
    assert seen["renamed"].title == "Внески 2026"  # the title is the file name

    assert [d.id for d in seen["earlier"]][:1] == [ids["first"]]
    assert seen["elsewhere"] == []  # versions are only looked for at the same place
    replaced = seen["replaced"]
    # Renamed above, so it is replaced under its new name.
    assert (replaced.replaced_title, replaced.replaced_author_id) == ("Внески 2026", SQUIRREL)

    assert seen["back"].exact_copy_of is None  # replaced texts may come back
    assert [d.id for d in seen["back_earlier"]][:1] == [ids["new"]]

    assert seen["states"] == {
        "first": DocStatus.SUPERSEDED,
        "rival": DocStatus.PENDING,
        "new": DocStatus.SUPERSEDED,
        "late": DocStatus.PENDING,
        "back": DocStatus.ACTIVE,
    }
    assert seen["back_scope"] == (ScopeLevel.MITTEN, "under_oak")
    # Drafts are never embedded; a document is embedded when it becomes current.
    assert seen["chunks"]["rival"] == seen["chunks"]["late"] == 0
    assert seen["chunks"]["first"] == seen["chunks"]["back"] == 1


async def _failing_suggest(title: str, text: str):
    raise RuntimeError("Groq is down")


async def _upload_without_llm():
    await register_user(SQUIRREL, "Білка")
    return await _upload(f"Правила толоки. Код {uuid.uuid4().hex}.", "Толока.txt", SQUIRREL)


def test_without_the_llm_the_author_picks_the_place(run_in_db, monkeypatch):
    monkeypatch.setattr(ingest, "suggest_place", _failing_suggest)
    upload = run_in_db(_upload_without_llm)
    assert upload.exact_copy_of is None and upload.suggested_place is None


async def _seed_twice() -> tuple:
    text = f"Правила толоки\n\nПрибираємо ліс щосуботи. Код {uuid.uuid4().hex}."
    return await seed_document(text.encode(), "a.txt"), await seed_document(text.encode(), "b.txt")


def test_archive_seeding_skips_texts_seen_before(run_in_db, monkeypatch):
    monkeypatch.setattr(ingest, "suggest_place", _fake_suggest)
    first, again = run_in_db(_seed_twice)
    assert first.place is not None and first.place.id == "under_oak" and not first.already_loaded
    assert again.already_loaded and again.place is None
