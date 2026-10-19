"""Answering: a question in plain text → advice from the current documents, with sources.

One function per step the bot waits on:

    place = await find_place(question)  # classify.py
    ...if None, ask the animal for the place: never guess a mitten
    answer = await answer_question(question, place.id)
"""

import logging
from dataclasses import dataclass

from forest_bot.application.answer.generate import write_answer
from forest_bot.application.answer.search import find_excerpts
from forest_bot.domain import CurrentDocument
from forest_bot.domain.forest_map import Place, forest_map
from forest_bot.infrastructure import db
from forest_bot.infrastructure.embedder import embedder
from forest_bot.settings import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Answer:
    place: Place
    text: str | None  # None: the advice for that place does not answer the question
    sources: list[CurrentDocument]  # source n is the one marked [n] in the text


async def answer_question(question: str, place_id: str) -> Answer:
    """Answer from the advice for the place and every broader place that includes it.
    Raises UnknownPlace."""
    place = forest_map.place(place_id)
    query = await embedder.embed_query(question)
    async with db.sessions() as session:
        excerpts = await find_excerpts(
            session, query, forest_map.place_and_broader(place), settings.answer_chunks_per_place
        )
    written = await write_answer(question, place, excerpts) if excerpts else None
    logger.info(
        "question at %s: found %s, cited %s",
        place.id,
        [e.document.id for e in excerpts],
        [e.document.id for e in written.sources] if written else "nothing",
    )
    if written is None:
        return Answer(place, None, [])
    return Answer(place, written.text, [CurrentDocument.of(e.document) for e in written.sources])
