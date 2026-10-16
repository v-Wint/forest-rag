from enum import StrEnum


class ScopeLevel(StrEnum):
    FOREST = "forest"
    PART = "part"
    MITTEN = "mitten"


class DocStatus(StrEnum):
    # Extracted and stored, place not assigned/confirmed yet; never used in answers.
    PENDING = "pending"
    ACTIVE = "active"
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
