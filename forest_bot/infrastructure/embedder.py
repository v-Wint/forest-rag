"""The sentence-embedding model (settings.embedding_model), loaded on first use.

Tokenizing and encoding are CPU-bound: call them off the event loop (asyncio.to_thread).
"""

import asyncio
from functools import cached_property

from sentence_transformers import SentenceTransformer

from forest_bot.settings import settings


class Embedder:
    def __init__(self, model_name: str, dim: int, passage_prefix: str, query_prefix: str) -> None:
        self.model_name = model_name
        self.dim = dim
        self._passage_prefix = passage_prefix
        self._query_prefix = query_prefix

    @cached_property
    def _model(self) -> SentenceTransformer:
        model = SentenceTransformer(self.model_name)
        if model.get_embedding_dimension() != self.dim:
            raise RuntimeError(
                f"{self.model_name} makes {model.get_embedding_dimension()}-dim vectors, "
                f"settings.embedding_dim is {self.dim}"
            )
        return model

    def load(self) -> None:
        """Load the model now; otherwise the first call that needs it does."""
        _ = self._model

    @property
    def max_tokens(self) -> int:
        if self._model.max_seq_length is None:
            raise RuntimeError(f"{self.model_name} does not say how many tokens it reads")
        return self._model.max_seq_length

    def count_tokens(self, text: str) -> int:
        """Tokens the model sees for a passage, prefix and special tokens included."""
        return len(self._model.tokenizer(self._passage_prefix + text)["input_ids"])

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._encode, [self._passage_prefix + t for t in texts])

    async def embed_query(self, text: str) -> list[float]:
        [vector] = await asyncio.to_thread(self._encode, [self._query_prefix + text])
        return vector

    def _encode(self, texts: list[str]) -> list[list[float]]:
        # Normalized: cosine similarity is then a plain inner product.
        return self._model.encode(texts, normalize_embeddings=True).tolist()


embedder = Embedder(
    settings.embedding_model,
    settings.embedding_dim,
    settings.embedding_passage_prefix,
    settings.embedding_query_prefix,
)
