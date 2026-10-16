from pydantic import BaseModel, ConfigDict, Field

from forest_bot.domain.enums import ExtractionMethod, FileKind


class ParsedDocument(BaseModel):
    """A file turned into clean, validated text: what the ETL hands to storage."""

    model_config = ConfigDict(frozen=True)

    source_filename: str
    file_kind: FileKind
    extraction_method: ExtractionMethod
    title: str
    text: str
    # Hash of the whitespace-collapsed text: identical content = identical hash,
    # regardless of file format or line wrapping.
    content_hash: str
    ocr_confidence: float | None = Field(default=None, ge=0, le=100)
