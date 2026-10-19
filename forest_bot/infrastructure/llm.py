"""The Groq chat model, created on first use: nothing needs GROQ_API_KEY until then."""

import re
from functools import cache

from langchain_groq import ChatGroq

from forest_bot.settings import settings

# Every tag that marks untrusted text (documents) in a prompt.
_DATA_TAGS = re.compile(r"<\s*/?\s*document\b[^>]*>", re.IGNORECASE)


@cache
def get_llm() -> ChatGroq:
    if settings.groq_api_key is None:
        raise RuntimeError("GROQ_API_KEY is not set")
    return ChatGroq(
        model=settings.llm_model,
        api_key=settings.groq_api_key,
        temperature=settings.llm_temperature,
        reasoning_effort=settings.llm_reasoning_effort,
        max_retries=settings.llm_max_retries,
    )


def as_data(tag: str, text: str) -> str:
    """Untrusted text in a <tag> block. Any data tags inside it are removed, so it cannot
    close its own block and write outside it, or open a block that looks like another."""
    return f"<{tag}>\n{_DATA_TAGS.sub('', text)}\n</{tag}>"
