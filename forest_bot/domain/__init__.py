# Importing every model here registers it on Base.metadata (needed by Alembic).
from forest_bot.domain.base import Base
from forest_bot.domain.chunks import EMBEDDING_DIM, Chunk
from forest_bot.domain.documents import Document
from forest_bot.domain.enums import DocStatus, ExtractionMethod, FileKind, ScopeLevel
from forest_bot.domain.extracted_text import ExtractedText
from forest_bot.domain.parsed_document import ParsedDocument
from forest_bot.domain.users import User

__all__ = [
    "EMBEDDING_DIM",
    "Base",
    "Chunk",
    "DocStatus",
    "Document",
    "ExtractedText",
    "ExtractionMethod",
    "FileKind",
    "ParsedDocument",
    "ScopeLevel",
    "User",
]
