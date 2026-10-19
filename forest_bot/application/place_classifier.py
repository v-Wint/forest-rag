"""Which place on the forest map a text is about, as the LLM sees it. Documents and
questions are classified the same way; only their prompts differ."""

from functools import cache
from typing import Literal

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field, create_model

from forest_bot.domain.forest_map import FOREST_ID, Place, forest_map
from forest_bot.infrastructure.llm import as_data, get_llm


async def classify_place(system_prompt: str, tag: str, text: str) -> Place | None:
    """The place the LLM picks for the text; None when it cannot tell."""
    answer = await _classifier().ainvoke(build_messages(system_prompt, tag, text))
    return forest_map.place(answer.place_id) if answer.place_id else None  # type: ignore[union-attr]


def build_messages(system_prompt: str, tag: str, text: str) -> list[BaseMessage]:
    """The prompt with the forest map filled in, then the text as data in a <tag> block."""
    system = system_prompt.format(places=forest_map.describe(), forest_id=FOREST_ID)
    return [SystemMessage(system), HumanMessage(as_data(tag, text))]


@cache
def _classifier():
    # Strict: Groq constrains decoding to the schema. Without it gpt-oss sometimes answers
    # with the schema itself instead of an object that follows it.
    return get_llm().with_structured_output(
        answer_schema(list(forest_map.places)), method="json_schema", strict=True
    )


def answer_schema(place_ids: list[str]) -> type[BaseModel]:
    """The only answers allowed: a place id from the map, or null."""
    return create_model(
        "PlaceAnswer",
        place_id=(
            Literal[tuple(place_ids)] | None,  # type: ignore[valid-type]
            Field(description="Id of the place, or null."),
        ),
    )
