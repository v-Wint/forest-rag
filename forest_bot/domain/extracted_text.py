from pydantic import BaseModel, ConfigDict, Field

from forest_bot.domain.enums import ExtractionMethod, FileKind


class ExtractedText(BaseModel):
    """Raw text read from a file: the one format every loader returns, whatever the source."""

    model_config = ConfigDict(frozen=True)

    text: str
    file_kind: FileKind
    method: ExtractionMethod
    # PDF and OCR text comes as visual lines that must be rejoined into paragraphs.
    needs_reflow: bool = False
    # Lowest page confidence (0–100), if any page was read with OCR.
    ocr_confidence: float | None = Field(default=None, ge=0, le=100)
