"""search.py's grouping, with the query for one place (_closest_chunks) replaced."""

import asyncio
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from forest_bot.application.answer import search
from forest_bot.application.answer.search import find_excerpts
from forest_bot.domain import Chunk, Document
from forest_bot.domain.forest_map import forest_map


def _chunks(document_id: int, *ordinals: int) -> list[Chunk]:
    document = Document(id=document_id, title=f"#{document_id}")
    return [
        Chunk(ordinal=o, text=f"{o}", document_id=document_id, document=document) for o in ordinals
    ]


def test_each_place_is_searched_on_its_own_most_specific_first(monkeypatch):
    closest = {
        "under_oak": _chunks(1, 0),
        "deciduous": _chunks(2, 0),
        "forest": [*_chunks(3, 4, 1), *_chunks(4, 0)],  # 3: a long guide, split
    }

    async def closest_chunks(session, query, place_id, limit):
        return closest[place_id][:limit]

    monkeypatch.setattr(search, "_closest_chunks", closest_chunks)
    places = forest_map.place_and_broader(forest_map.place("under_oak"))

    excerpts = asyncio.run(find_excerpts(cast(AsyncSession, None), [1.0], places, per_place=3))

    assert [(e.document.id, e.place.id) for e in excerpts] == [
        (1, "under_oak"),
        (2, "deciduous"),
        (3, "forest"),  # both pieces of the guide, one excerpt
        (4, "forest"),
    ]
    assert excerpts[2].text == "1\n…\n4"
