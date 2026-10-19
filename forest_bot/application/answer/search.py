"""Search: the chunks of current advice closest to the question, place by place.

Each place whose advice applies is searched on its own, so a relevant mitten document is
never pushed out by broader ones. Filtering by place does most of the work: documents of
different places follow the same templates (two mittens' charters embed 0.96 alike),
while at one place they are about different things.

The place is filtered first through B-tree indexes (documents by status and place, chunks
by document), then every chunk there is compared with the question exactly: what pgvector
recommends when a filter matches a small share of the rows. An approximate (HNSW) index
would find the nearest chunks of the whole forest and filter them after, so it could
return too few from one place, while a place holds at most a few hundred chunks, which
take well under a millisecond to compare. Should one place grow to many thousands, HNSW
with pgvector's iterative scan is the next step."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from forest_bot.domain import Chunk, DocStatus, Document
from forest_bot.domain.forest_map import Place


@dataclass(slots=True)
class Excerpt:
    """A document and its chunks that were found, in the document's order."""

    document: Document
    place: Place
    chunks: list[Chunk] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n…\n".join(chunk.text for chunk in sorted(self.chunks, key=lambda c: c.ordinal))


async def find_excerpts(
    session: AsyncSession, query: list[float], places: Sequence[Place], per_place: int
) -> list[Excerpt]:
    """The closest `per_place` chunks at each place, grouped by document; places in the
    given order (most specific first), documents by relevance within a place."""
    excerpts: dict[int, Excerpt] = {}
    for place in places:
        for chunk in await _closest_chunks(session, query, place.id, per_place):
            excerpt = excerpts.setdefault(chunk.document_id, Excerpt(chunk.document, place))
            excerpt.chunks.append(chunk)
    return list(excerpts.values())


async def _closest_chunks(
    session: AsyncSession, query: list[float], place_id: str, limit: int
) -> Sequence[Chunk]:
    chunks = await session.scalars(
        select(Chunk)
        .join(Chunk.document)
        .where(Document.status == DocStatus.ACTIVE, Document.scope_id == place_id)
        .order_by(Chunk.embedding.cosine_distance(query))
        .limit(limit)
        .options(selectinload(Chunk.document).selectinload(Document.author))
    )
    return chunks.all()
