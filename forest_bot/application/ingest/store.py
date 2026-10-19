"""The `documents` table. Every function runs inside the caller's transaction."""

from collections.abc import Sequence

from sqlalchemy import exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from forest_bot.domain import DocStatus, Document, ParsedDocument
from forest_bot.domain.forest_map import Place


async def save_draft(
    session: AsyncSession, document: ParsedDocument, *, author_id: int | None
) -> Document:
    """Always a new `pending` row, even for a text stored before."""
    draft = Document(
        title=document.title,
        author_id=author_id,
        source_filename=document.source_filename,
        file_kind=document.file_kind,
        extraction_method=document.extraction_method,
        ocr_confidence=document.ocr_confidence,
        content_hash=document.content_hash,
        full_text=document.text,
    )
    session.add(draft)
    await session.flush()
    await session.refresh(draft)  # the server-side upload time
    return draft


async def find_active_with_same_text(session: AsyncSession, content_hash: str) -> Document | None:
    return await session.scalar(
        select(Document)
        .where(Document.content_hash == content_hash, Document.status == DocStatus.ACTIVE)
        .options(selectinload(Document.author))
    )


async def archive_file_loaded(session: AsyncSession, filename: str) -> bool:
    """An archive file seeded before: active now, or replaced since."""
    return bool(
        await session.scalar(
            select(
                exists().where(
                    Document.author_id.is_(None),
                    Document.source_filename == filename,
                    Document.status != DocStatus.PENDING,
                )
            )
        )
    )


async def was_ever_active(session: AsyncSession, content_hash: str) -> bool:
    """Active now, or replaced since."""
    return bool(
        await session.scalar(
            select(
                exists().where(
                    Document.content_hash == content_hash, Document.status != DocStatus.PENDING
                )
            )
        )
    )


async def list_active_at(session: AsyncSession, place_id: str) -> Sequence[Document]:
    documents = await session.scalars(
        select(Document)
        .where(Document.scope_id == place_id, Document.status == DocStatus.ACTIVE)
        .options(selectinload(Document.author))
        .order_by(Document.id)
    )
    return documents.all()


async def activate_if_draft(session: AsyncSession, document_id: int, place: Place) -> bool:
    """False if it is not a draft any more. Raises IntegrityError if the same text is
    active already (the partial unique index)."""
    activated = await session.scalar(
        update(Document)
        .where(Document.id == document_id, Document.status == DocStatus.PENDING)
        .values(status=DocStatus.ACTIVE, scope_level=place.level, scope_id=place.id)
        .returning(Document.id)
    )
    return activated is not None


async def supersede_if_active_at(
    session: AsyncSession, document_id: int, place_id: str
) -> Document | None:
    """The superseded document; None if it is not active at that place any more."""
    return await session.scalar(
        update(Document)
        .where(
            Document.id == document_id,
            Document.status == DocStatus.ACTIVE,
            Document.scope_id == place_id,
        )
        .values(status=DocStatus.SUPERSEDED)
        .returning(Document)
    )
