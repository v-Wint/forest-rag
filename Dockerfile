# Three stages; only the last one is the image that runs.

# 1. The Forest Archive, downloaded from Google Drive. Docker keeps the result of this step
#    and reuses it, so each machine downloads the archive once.
FROM python:3.14-slim-trixie AS archive
ARG ARCHIVE_FOLDER_ID=1b_hEjnkQfP8ZVP-OEbnYWqoGSFwXMAP3
COPY pipelines/download_archive.py .
RUN python download_archive.py "$ARCHIVE_FOLDER_ID" /archive

# 2. The Python dependencies, installed by uv into /app/.venv.
FROM python:3.14-slim-trixie AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.25 /uv /usr/local/bin/uv
WORKDIR /app
# The image's own Python: uv must not download another one, which the final image would lack.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 3. The image that runs: Tesseract, the dependencies, the archive and the code.
FROM python:3.14-slim-trixie
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-ukr \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home forest \
    && mkdir /models && chown forest /models
WORKDIR /app
COPY --from=builder /app/.venv .venv
COPY --from=archive /archive archive
COPY . .

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    ARCHIVE_DIR=/app/archive \
    # The embedding model is downloaded here on the first start (compose keeps it in a volume).
    HF_HOME=/models
USER forest

# Every start: update the schema, seed the archive (only the first start finds new files),
# then run the bot.
CMD ["sh", "-c", "alembic upgrade head && python -m pipelines.ingest && exec python -m bot"]
