from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forest_bot.domain.base import Base
from forest_bot.settings import settings

if TYPE_CHECKING:
    from forest_bot.domain.documents import Document


class Chunk(Base):
    """A piece of a document as embedded. There is no vector index on purpose: every search
    is within one place, found through the documents' (status, scope_id) index, and the
    distance to each of that place's chunks is computed exactly (see answer/search.py)."""

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int]
    # The text that was embedded. A document that was split repeats its title at the start
    # of every piece, so each piece still says which document it comes from.
    text: Mapped[str]
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim))

    document: Mapped[Document] = relationship(back_populates="chunks")
