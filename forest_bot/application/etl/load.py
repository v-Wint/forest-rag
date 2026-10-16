"""Load: store a parsed document in the `documents` table."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from forest_bot.domain import Document, ParsedDocument


@dataclass(frozen=True, slots=True)
class SaveResult:
    document_id: int
    created: bool  # False: a document with identical text was already stored


async def save_document(
    session: AsyncSession, document: ParsedDocument, *, author_id: int | None = None
) -> SaveResult:
    """Store the document as `pending` unless identical text is already stored.
    Runs inside the caller's transaction."""
    # ON CONFLICT keeps this idempotent, even for two identical uploads at once.
    new_id = await session.scalar(
        insert(Document)
        .values(
            title=document.title,
            author_id=author_id,
            source_filename=document.source_filename,
            file_kind=document.file_kind,
            extraction_method=document.extraction_method,
            ocr_confidence=document.ocr_confidence,
            content_hash=document.content_hash,
            full_text=document.text,
        )
        .on_conflict_do_nothing(index_elements=[Document.content_hash])
        .returning(Document.id)
    )
    if new_id is not None:
        return SaveResult(new_id, created=True)
    existing_id = await session.scalar(
        select(Document.id).where(Document.content_hash == document.content_hash)
    )
    return SaveResult(existing_id, created=False)
