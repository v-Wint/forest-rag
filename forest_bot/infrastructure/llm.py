"""The Groq chat model, created on first use: nothing needs GROQ_API_KEY until then."""

from functools import cache

from langchain_groq import ChatGroq

from forest_bot.settings import settings


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
