from enum import StrEnum


class FailureReason(StrEnum):
    UNSUPPORTED = "unsupported"
    TOO_LARGE = "too_large"
    CORRUPT = "corrupt"
    EMPTY = "empty"
    UNREADABLE_SCAN = "unreadable_scan"


class ExtractionError(Exception):
    """A file could not be turned into a document. `reason` tells the bot what to say."""

    def __init__(self, reason: FailureReason, detail: str) -> None:
        self.reason = reason
        super().__init__(f"{reason}: {detail}")


class NotTheAuthor(PermissionError):
    """Only the animal who uploaded a document chooses its place."""


class AlreadyHandled(Exception):
    """The draft is not waiting any more: it was activated already (a button pressed twice)."""


class AlreadyCurrent(Exception):
    """The same text became current while the author was deciding (another animal's upload)."""


class DocumentsChanged(Exception):
    """The document to be replaced is not current any more: someone replaced it meanwhile."""
