"""Seed the database with every file in settings.archive_dir, the Forest Archive.

Archive documents have no author to ask, so the LLM's place is final and nothing is
replaced. A file or text loaded before is skipped, so re-running is safe and fast (the bot's
Docker image runs it on every start); a document the LLM cannot place is not used, and is
tried again on the next run.

uv run python -m pipelines.ingest
"""

import asyncio
import logging
from collections import Counter
from pathlib import Path

from forest_bot.application.ingest import ExtractionError, seed_document
from forest_bot.application.startup import running, setup_logging
from forest_bot.settings import settings

logger = logging.getLogger("ingest")


async def ingest_pipeline(data_dir: Path) -> Counter[str]:
    outcomes: Counter[str] = Counter()
    for path in sorted(p for p in data_dir.iterdir() if p.is_file()):
        outcomes[await _ingest_file(path)] += 1
    return outcomes


async def _ingest_file(path: Path) -> str:
    # A bad file never takes the others down with it.
    try:
        seeded = await seed_document(path.read_bytes(), path.name)
    except ExtractionError as exc:
        logger.warning("skipped %s: %s", path.name, exc)
        return exc.reason.value
    except Exception:  # a bug or an outside failure (OCR, database, LLM): log it, keep going
        logger.exception("failed %s", path.name)
        return "failed"
    if seeded.already_loaded:
        outcome = "already_loaded"
    elif seeded.place is None:
        outcome = "place_unclear"
    else:
        outcome = f"placed in {seeded.place.id}"
    logger.info("%s %s", outcome, path.name)
    return outcome


async def main() -> None:
    async with running():
        outcomes = await ingest_pipeline(settings.archive_dir)
    logger.info("done: %s", dict(outcomes))


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())
