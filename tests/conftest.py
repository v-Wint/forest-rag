import io
from collections.abc import Callable

import docx
import pytest


@pytest.fixture
def make_docx() -> Callable[..., bytes]:
    def make(*paragraphs: str) -> bytes:
        document = docx.Document()
        for paragraph in paragraphs:
            document.add_paragraph(paragraph)
        buffer = io.BytesIO()
        document.save(buffer)
        return buffer.getvalue()

    return make
