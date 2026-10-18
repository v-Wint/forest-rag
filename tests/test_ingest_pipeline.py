import asyncio

import pipelines.ingest
from forest_bot.application.ingest import ExtractionError, FailureReason, Seeded
from forest_bot.domain.forest_map import forest_map
from pipelines.ingest import ingest_pipeline


async def _fake_seed(data: bytes, filename: str) -> Seeded:
    if data == b"boom":
        raise RuntimeError("bug somewhere in ingestion")
    if not data.strip():
        raise ExtractionError(FailureReason.EMPTY, "no text")
    if data == b"old":
        return Seeded("Старий", None, already_loaded=True)
    if data == b"vague":
        return Seeded("Неясний", None)
    return Seeded("Новий", forest_map.places["under_oak"])


def test_every_outcome_is_counted_and_a_failure_does_not_stop_the_rest(tmp_path, monkeypatch):
    monkeypatch.setattr(pipelines.ingest, "seed_document", _fake_seed)
    files = {"a": b"new", "b": b"boom", "c": b"  ", "d": b"old", "e": b"vague", "f": b"new"}
    for name, data in files.items():
        (tmp_path / f"{name}.txt").write_bytes(data)

    outcomes = asyncio.run(ingest_pipeline(tmp_path))

    assert outcomes == {
        "placed in under_oak": 2,
        "failed": 1,
        "empty": 1,
        "already_loaded": 1,
        "place_unclear": 1,
    }
