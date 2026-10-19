from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """All configuration and secrets come from environment variables (or a local .env)."""

    # Found from any working directory; a missing file is fine (e.g. in Docker).
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    postgres_user: str = "forest"
    postgres_password: SecretStr
    postgres_db: str = "forest"
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432

    log_level: str = "INFO"

    # Upload limits. Telegram bots cannot download files over 20 MB anyway.
    max_file_bytes: int = 20 * 1024 * 1024
    max_text_chars: int = 500_000
    max_pdf_pages: int = 300
    # A .docx is a zip: what it may unpack to (zip bombs).
    max_docx_unpacked_bytes: int = 100 * 1024 * 1024
    max_docx_entries: int = 2_000

    # Path to the tesseract binary if it is not on PATH (e.g. on Windows).
    tesseract_cmd: str | None = None
    ocr_lang: str = "ukr"
    # Scanned pages with lower mean word confidence (0–100) are rejected as unreadable.
    ocr_min_confidence: float = 60.0
    # A PDF page with fewer letters than this in its text layer is a scanned image.
    min_letters_for_text_layer: int = 20
    # Scanned pages are rendered at this resolution for OCR.
    ocr_render_dpi: int = 300
    # Binarization thresholds (gray levels) tried on every scanned page; the most confident
    # result wins. Measured on the Forest Archive scans: any single threshold misses some
    # facts (e.g. the digit 3 read as the letter «З»). With Tesseract 5.5.3 at 300 DPI the
    # best of these still misreads one digit in 19 scans («до 5 числа» → «до 9 числа»).
    ocr_thresholds: tuple[int, ...] = (90, 100, 110)

    embedding_model: str = "intfloat/multilingual-e5-base"
    # Must match the model. The chunks.embedding column is created with it, so changing
    # the model means a migration and re-embedding every document.
    embedding_dim: int = 768
    # e5 models were trained with these prefixes; set both to "" for a model without them.
    embedding_passage_prefix: str = "passage: "
    embedding_query_prefix: str = "query: "
    # Overlap between the pieces of a split document, as a share of the model's max tokens.
    chunk_overlap: float = 0.1

    # An upload may be a new version of a current document at the same place when this
    # share of its file name's topic words, or of its content, is shared (see the README).
    version_name_threshold: float = 0.33
    version_content_threshold: float = 0.3

    # Answers: the chunks found for each place whose advice applies (a mitten, its parts,
    # the whole forest). A document that fits the embedding model is one chunk.
    answer_chunks_per_place: int = 3
    max_question_chars: int = 500

    groq_api_key: SecretStr | None = None
    llm_model: str = "openai/gpt-oss-120b"
    llm_temperature: float = 0.0
    # For reasoning models (gpt-oss: "low" / "medium" / "high"); None for other models.
    llm_reasoning_effort: str | None = "low"
    # Free-tier rate limits answer 429: the client retries with backoff this many times.
    llm_max_retries: int = 5

    telegram_bot_token: SecretStr | None = None
    # The real name an animal gives is shown next to its advice in every answer.
    max_name_chars: int = 50

    # The places a document can apply to; see the file itself.
    forest_map_path: Path = PROJECT_ROOT / "forest_map.toml"
    # The Forest Archive files, not part of the repository: what the bot starts with
    # (pipelines.ingest loads it).
    archive_dir: Path = PROJECT_ROOT / "data" / "archive"

    @property
    def database_url(self) -> URL:
        # URL.create escapes special characters in the password, unlike string formatting.
        return URL.create(
            "postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


settings = Settings()  # type: ignore
