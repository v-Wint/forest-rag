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
