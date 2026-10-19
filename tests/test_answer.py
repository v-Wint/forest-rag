"""answer.py with the search, the embedding model and the LLM replaced (see the fake_db
fixture for the database)."""

import asyncio
from datetime import UTC, datetime

import pytest

import forest_bot.application.answer.answer as answering
from forest_bot.application.answer import answer_question
from forest_bot.application.answer.generate import cite
from forest_bot.application.answer.search import Excerpt
from forest_bot.domain import Chunk, DocStatus, Document
from forest_bot.domain.forest_map import forest_map
from forest_bot.infrastructure.embedder import embedder

OAK = forest_map.place("under_oak")


def _excerpt(id: int, title: str) -> Excerpt:
    document = Document(
        id=id,
        title=title,
        status=DocStatus.ACTIVE,
        scope_level=OAK.level,
        scope_id=OAK.id,
        uploaded_at=datetime(2026, 9, 12, tzinfo=UTC),
        source_filename=f"{title}.txt",
    )
    return Excerpt(document, OAK, [Chunk(ordinal=0, text=f"{title}: 4 жолуді.")])


DUES, WINTER = _excerpt(7, "Членські внески"), _excerpt(8, "Внески на зиму")


@pytest.fixture(autouse=True)
def no_embedding_model(monkeypatch):
    async def embed_query(text: str) -> list[float]:
        return [1.0]

    monkeypatch.setattr(embedder, "embed_query", embed_query)


def _search_finds(monkeypatch, excerpts: list[Excerpt]) -> list[str]:
    """The ids of the places searched, filled in when the search runs."""
    searched = []

    async def find_excerpts(session, query, places, per_place):
        searched.extend(p.id for p in places)
        return excerpts

    monkeypatch.setattr(answering, "find_excerpts", find_excerpts)
    return searched


def test_the_sources_are_the_documents_the_answer_cites(fake_db, monkeypatch):
    _search_finds(monkeypatch, [DUES, WINTER])

    async def write_answer(question, place, excerpts):
        return cite("Взимку 5 жолудів [2].", excerpts)

    monkeypatch.setattr(answering, "write_answer", write_answer)

    answer = asyncio.run(answer_question("Скільки внесок узимку?", "under_oak"))

    assert answer.text == "Взимку 5 жолудів [1]."
    assert [(s.id, s.title, s.author_name) for s in answer.sources] == [
        (8, "Внески на зиму", None)  # from the Forest Archive
    ]


def test_a_part_is_answered_from_its_own_and_the_forest_advice(fake_db, monkeypatch):
    searched = _search_finds(monkeypatch, [])
    asyncio.run(answer_question("Скільки внесок?", "deciduous"))
    assert searched == ["deciduous", "forest"]  # never its mittens'


def test_nothing_found_is_no_answer_without_asking_the_llm(fake_db, monkeypatch):
    _search_finds(monkeypatch, [])

    async def write_answer(question, place, excerpts):
        raise AssertionError("must not be called")

    monkeypatch.setattr(answering, "write_answer", write_answer)

    answer = asyncio.run(answer_question("Скільки внесок?", "under_oak"))

    assert (answer.place, answer.text, answer.sources) == (OAK, None, [])
