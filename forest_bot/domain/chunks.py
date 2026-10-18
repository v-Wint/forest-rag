from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forest_bot.domain.base import Base
from forest_bot.settings import settings

if TYPE_CHECKING:
    from forest_bot.domain.documents import Document


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        # Approximate nearest-neighbour search by cosine distance (the `<=>` operator).
        # HNSW, unlike IVFFlat, needs no training data, so it can be created on an empty table.
        Index(
            "ix_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

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
