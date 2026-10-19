from dataclasses import dataclass
from datetime import datetime
from typing import Self

from forest_bot.domain.documents import Document
from forest_bot.domain.forest_map import Place, forest_map


@dataclass(frozen=True, slots=True)
class CurrentDocument:
    """An active document, as the bot shows it to animals."""

    id: int
    title: str
    place: Place
    author_name: str | None  # None: from the Forest Archive
    uploaded_at: datetime
    filename: str

    @classmethod
    def of(cls, active: Document) -> Self:
        """The document's author must be loaded."""
        assert active.scope_id is not None, "an active document always has a place"
        return cls(
            id=active.id,
            title=active.title,
            place=forest_map.place(active.scope_id),
            author_name=active.author.real_name if active.author else None,
            uploaded_at=active.uploaded_at,
            filename=active.source_filename,
        )
