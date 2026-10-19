"""Ingestion: a file from an animal (or the archive) becomes advice used in answers.

One function per decision the bot asks the author for:

    upload = await upload_document(data, filename, author_id=...)
    if upload.exact_copy_of:  ...say where it is; if the file name differs, offer
                              await rename_current(upload.document_id, author_id=...)
    else:                     ...ask for the place, suggesting upload.suggested_place
    earlier = await find_earlier_versions(upload.document_id, place_id, author_id=...)
    ...if any, ask whether this one replaces one of them
    await activate(upload.document_id, place_id, replaces_id=..., author_id=...)

seed_document() does the same for a Forest Archive file, with no author to ask.
"""

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from forest_bot.application.ingest import store
from forest_bot.application.ingest.classify import suggest_place
from forest_bot.application.ingest.embed import embed_document
from forest_bot.application.ingest.errors import (
    AlreadyCurrent,
    AlreadyHandled,
    DocumentsChanged,
    NotTheAuthor,
)
from forest_bot.application.ingest.extractors import extract
from forest_bot.application.ingest.transform import transform
from forest_bot.application.ingest.versions import Match, find_versions
from forest_bot.domain import Chunk, CurrentDocument, DocStatus, Document, ParsedDocument
from forest_bot.domain.forest_map import Place, forest_map
from forest_bot.infrastructure import db

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Upload:
    document_id: int
    title: str
    suggested_place: Place | None
    # The draft then only keeps the new file name, for rename_current().
    exact_copy_of: CurrentDocument | None = None


@dataclass(frozen=True, slots=True)
class Activated:
    title: str
    place: Place
    replaced_title: str | None = None
    replaced_author_id: int | None = None


@dataclass(frozen=True, slots=True)
class Seeded:
    title: str
    place: Place | None  # None: the LLM could not tell; tried again on the next run
    already_loaded: bool = False


def parse_file(data: bytes, filename: str) -> ParsedDocument:
    return transform(extract(data), filename)


async def upload_document(data: bytes, filename: str, *, author_id: int) -> Upload:
    parsed = await _parse_off_the_event_loop(data, filename)
    async with db.sessions.begin() as session:
        draft = await store.save_draft(session, parsed, author_id=author_id)
        exact_copy = await store.find_active_with_same_text(session, draft.content_hash)
    if exact_copy is not None:
        return Upload(draft.id, draft.title, None, exact_copy_of=CurrentDocument.of(exact_copy))
    return Upload(draft.id, draft.title, await _suggest_place_unless_llm_fails(draft))


async def rename_current(document_id: int, *, author_id: int) -> CurrentDocument:
    """The active document with the draft's text takes the draft's file name.
    Raises NotTheAuthor, AlreadyHandled or DocumentsChanged (that text was replaced)."""
    async with db.sessions.begin() as session:
        draft = await _own_draft(session, document_id, author_id)
        active = await store.find_active_with_same_text(session, draft.content_hash)
        if active is None:
            raise DocumentsChanged(f"the text of document #{document_id} is not active")
        active.source_filename, active.title = draft.source_filename, draft.title
        return CurrentDocument.of(active)


async def find_earlier_versions(
    document_id: int, place_id: str, *, author_id: int
) -> list[CurrentDocument]:
    """Active documents at the place the draft may be a new version of, most similar first.
    Raises UnknownPlace, NotTheAuthor or AlreadyHandled."""
    place = forest_map.place(place_id)
    async with db.sessions() as session:
        draft = await _own_draft(session, document_id, author_id)
        active_there = await store.list_active_at(session, place.id)
    matches = find_versions(draft, active_there)
    _log_version_scores(draft, place, matches)
    return [CurrentDocument.of(match.document) for match in matches]


async def activate(
    document_id: int,
    place_id: str,
    *,
    replaces_id: int | None = None,
    author_id: int | None,
) -> Activated:
    """The draft is used in answers at the place from now on, instead of `replaces_id`.
    Raises UnknownPlace, NotTheAuthor, AlreadyHandled, AlreadyCurrent (the same text became
    active meanwhile) or DocumentsChanged (`replaces_id` was replaced meanwhile)."""
    place = forest_map.place(place_id)
    async with db.sessions() as session:
        draft = await _own_draft(session, document_id, author_id)
    chunks = await embed_document(draft)
    replaced = await _swap_in(draft, place, chunks, replaces_id)
    logger.info(
        "document #%d is active at %s%s",
        document_id,
        place.id,
        "" if replaces_id is None else f", replacing #{replaces_id}",
    )
    if replaced is None:
        return Activated(draft.title, place)
    return Activated(draft.title, place, replaced.title, replaced.author_id)


async def seed_document(data: bytes, filename: str) -> Seeded:
    """A Forest Archive file: the LLM's place is final and nothing is replaced. A text that
    was ever active is skipped, so a re-run never brings back a replaced archive document."""
    parsed = await _parse_off_the_event_loop(data, filename)
    async with db.sessions.begin() as session:
        if await store.was_ever_active(session, parsed.content_hash):
            return Seeded(parsed.title, None, already_loaded=True)
        draft = await store.save_draft(session, parsed, author_id=None)
    place = await suggest_place(draft.title, draft.full_text)
    if place is not None:
        await activate(draft.id, place.id, author_id=None)
    return Seeded(draft.title, place)


async def _parse_off_the_event_loop(data: bytes, filename: str) -> ParsedDocument:
    """OCR of a scan takes seconds; the bot keeps answering others meanwhile."""
    return await asyncio.to_thread(parse_file, data, filename)


async def _suggest_place_unless_llm_fails(draft: Document) -> Place | None:
    """The author picks the place anyway, so a failed LLM call only loses the suggestion."""
    try:
        return await suggest_place(draft.title, draft.full_text)
    except Exception:
        logger.exception("no place suggestion for document #%d", draft.id)
        return None


async def _own_draft(session: AsyncSession, document_id: int, author_id: int | None) -> Document:
    draft = await session.get_one(Document, document_id)
    if draft.author_id != author_id:
        raise NotTheAuthor(f"document #{document_id} is not by {author_id}")
    if draft.status != DocStatus.PENDING:
        raise AlreadyHandled(f"document #{document_id} is {draft.status}")
    return draft


async def _swap_in(
    draft: Document, place: Place, chunks: Sequence[Chunk], replaces_id: int | None
) -> Document | None:
    """One transaction, so answers never see both versions or neither. Returns the
    replaced document."""
    try:
        async with db.sessions.begin() as session:
            replaced = None
            if replaces_id is not None:
                replaced = await store.supersede_if_active_at(session, replaces_id, place.id)
                if replaced is None:
                    raise DocumentsChanged(f"#{replaces_id} is not active at {place.id}")
            if not await store.activate_if_draft(session, draft.id, place):
                raise AlreadyHandled(f"document #{draft.id} was activated meanwhile")
            session.add_all(chunks)
    except IntegrityError as exc:
        raise AlreadyCurrent(f"the text of document #{draft.id} is active already") from exc
    return replaced


def _log_version_scores(draft: Document, place: Place, matches: list[Match]) -> None:
    """With the author's answer (logged by activate), shows whether the thresholds hold."""
    scores = ", ".join(
        f"#{m.document.id} (name {m.name_score:.2f}, content {m.content_score:.2f})"
        for m in matches
    )
    logger.info(
        "document #%d at %s may replace: %s", draft.id, place.id, scores or "no earlier versions"
    )
