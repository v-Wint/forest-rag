import asyncio
from contextlib import asynccontextmanager

import pipelines.etl
from forest_bot.application.etl import ExtractionError, FailureReason, SaveResult
from pipelines.etl import etl_pipeline


class FakeSessions:
    @asynccontextmanager
    async def begin(self):
        yield None


async def _fake_ingest(session, data: bytes, filename: str) -> SaveResult:
    if data == b"boom":
        raise RuntimeError("bug somewhere in the ETL")
    if not data.strip():
        raise ExtractionError(FailureReason.EMPTY, "no text")
    return SaveResult(1, created=True)


def test_one_failing_file_does_not_stop_the_others(tmp_path, monkeypatch):
    monkeypatch.setattr(pipelines.etl, "ingest_document", _fake_ingest)
    for name, data in [("a.txt", b"text"), ("b.txt", b"boom"), ("c.txt", b"  "), ("d.txt", b"x")]:
        (tmp_path / name).write_bytes(data)

    outcomes = asyncio.run(etl_pipeline(tmp_path, FakeSessions()))

    assert outcomes == {"loaded": 2, "failed": 1, "empty": 1}
