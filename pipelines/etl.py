"""ETL over settings.data_dir: every file → normalized document in `documents` (pending).

uv run python -m pipelines.etl
"""

import asyncio
import logging
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from forest_bot.application.etl import ExtractionError, ingest_document
from forest_bot.application.etl.extractors import ocr
from forest_bot.infrastructure import db
from forest_bot.settings import settings

logger = logging.getLogger("etl")


async def etl_pipeline(data_dir: Path, sessions: async_sessionmaker[AsyncSession]) -> Counter[str]:
    outcomes: Counter[str] = Counter()
    for path in sorted(p for p in data_dir.iterdir() if p.is_file()):
        outcomes[await _ingest_file(path, sessions)] += 1
    return outcomes


async def _ingest_file(path: Path, sessions: async_sessionmaker[AsyncSession]) -> str:
    # One transaction per file: a bad file never takes the others down with it.
    try:
        async with sessions.begin() as session:
            result = await ingest_document(session, path.read_bytes(), path.name)
    except ExtractionError as exc:
        logger.warning("skipped %s: %s", path.name, exc)
        return exc.reason.value
    except Exception:  # a bug or an outside failure (OCR, database): log it, keep going
        logger.exception("failed %s", path.name)
        return "failed"
    outcome = "loaded" if result.created else "already_loaded"
    logger.info("%s %s → document #%d", outcome, path.name, result.document_id)
    return outcome


async def main() -> None:
    ocr.check_available()  # fail now, not on the first scanned file
    try:
        outcomes = await etl_pipeline(settings.data_dir, db.sessions)
    finally:
        await db.engine.dispose()
    logger.info("done: %s", dict(outcomes))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # Cyrillic file names in the log: the Windows console is not UTF-8 by default.
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    asyncio.run(main())
