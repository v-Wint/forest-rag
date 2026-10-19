"""Ingestion's public surface: what the bot and the pipeline use. ingest.py tells the whole
story; the other modules are its steps, imported directly only to test one."""

from forest_bot.application.ingest.errors import (
    AlreadyCurrent,
    AlreadyHandled,
    DocumentsChanged,
    ExtractionError,
    FailureReason,
    NotTheAuthor,
)
from forest_bot.application.ingest.ingest import (
    Activated,
    Seeded,
    Upload,
    activate,
    find_earlier_versions,
    rename_current,
    seed_document,
    upload_document,
)

__all__ = [
    "Activated",
    "AlreadyCurrent",
    "AlreadyHandled",
    "DocumentsChanged",
    "ExtractionError",
    "FailureReason",
    "NotTheAuthor",
    "Seeded",
    "Upload",
    "activate",
    "find_earlier_versions",
    "rename_current",
    "seed_document",
    "upload_document",
]
