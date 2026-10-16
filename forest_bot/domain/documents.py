from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forest_bot.domain.base import Base
from forest_bot.domain.enums import DocStatus, ExtractionMethod, FileKind, ScopeLevel

if TYPE_CHECKING:
    from forest_bot.domain.chunks import Chunk
    from forest_bot.domain.users import User


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_status_scope", "status", "scope_id"),
        # A document can only take part in answers once its place is known.
        CheckConstraint(
            "status = 'pending' OR (scope_level IS NOT NULL AND scope_id IS NOT NULL)",
            name="scope_required_unless_pending",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    status: Mapped[DocStatus] = mapped_column(default=DocStatus.PENDING)
    scope_level: Mapped[ScopeLevel | None]
    # Place id from the forest map config ("forest", "coniferous", "under_oak", ...).
    # Plain text on purpose: the map lives in config, so changing it needs no migration.
    scope_id: Mapped[str | None]
    # NULL for documents from the Forest Archive, which have no known author.
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.telegram_id"))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    source_filename: Mapped[str]
    file_kind: Mapped[FileKind]
    extraction_method: Mapped[ExtractionMethod]
    ocr_confidence: Mapped[float | None]
    content_hash: Mapped[str] = mapped_column(unique=True)
    full_text: Mapped[str]
    superseded_by_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    file_path: Mapped[str | None]

    author: Mapped[User | None] = relationship(back_populates="documents")
    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Chunk.ordinal"
    )
