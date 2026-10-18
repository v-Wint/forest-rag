"""Activate, first half: a document → its embedded chunks, the rows retrieval searches.

A document that fits the embedding model is one chunk; a longer one is split into pieces
that do, because the model silently truncates longer input."""

import asyncio
from collections.abc import Callable

from langchain_text_splitters import RecursiveCharacterTextSplitter

from forest_bot.domain import Chunk, Document
from forest_bot.infrastructure.embedder import embedder
from forest_bot.settings import settings

# Paragraphs first, then lines (list items), sentences, words.
_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


async def embed_document(document: Document) -> list[Chunk]:
    """Split a stored document and embed the pieces. The chunks are not added to any
    session: embedding a long guide takes seconds, so it happens before the transaction
    that stores them."""
    # Tokenizing (and loading the model on first use) is CPU-bound: keep it off the event loop.
    pieces = await asyncio.to_thread(_split, document)
    vectors = await embedder.embed_passages(pieces)
    return [
        Chunk(document_id=document.id, ordinal=i, text=text, embedding=vector)
        for i, (text, vector) in enumerate(zip(pieces, vectors, strict=True))
    ]


def _split(document: Document) -> list[str]:
    return split_document(
        document.full_text,
        document.title,
        embedder.count_tokens,
        embedder.max_tokens,
        settings.chunk_overlap,
    )


def split_document(
    text: str,
    title: str,
    count_tokens: Callable[[str], int],
    max_tokens: int,
    overlap: float,
) -> list[str]:
    """The whole text if it fits the model; otherwise pieces that do, overlapping by
    `overlap` × max_tokens. Every piece starts with the document title, so it still says
    where it comes from."""
    if count_tokens(text) <= max_tokens:
        return [text]

    header = f"{title}\n\n"
    splitter = RecursiveCharacterTextSplitter(
        separators=_SEPARATORS,
        keep_separator="end",
        chunk_size=max_tokens - count_tokens(header),
        chunk_overlap=int(max_tokens * overlap),
        length_function=count_tokens,
    )
    # Split the body only: a title line left in it can come out as a chunk of its own.
    body = text.removeprefix(title).lstrip()
    return [header + piece for piece in splitter.split_text(body)]
