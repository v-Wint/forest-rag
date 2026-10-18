from enum import StrEnum


class ScopeLevel(StrEnum):
    FOREST = "forest"
    PART = "part"
    MITTEN = "mitten"


class DocStatus(StrEnum):
    # A draft: stored, waiting for its author to confirm the place. Counts for nothing:
    # not embedded, never used in answers, ignored when checking for copies and versions.
    PENDING = "pending"
    # Current advice: embedded and used in answers.
    ACTIVE = "active"
    # Replaced by a newer version. Kept, never used in answers.
    SUPERSEDED = "superseded"


class FileKind(StrEnum):
    TXT = "txt"
    DOCX = "docx"
    PDF = "pdf"


class ExtractionMethod(StrEnum):
    PLAIN_TEXT = "plain_text"
    DOCX = "docx"
    PDF_TEXT_LAYER = "pdf_text_layer"
    OCR = "ocr"
    PDF_MIXED = "pdf_mixed"  # some pages from the text layer, some via OCR
