from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """All configuration and secrets come from environment variables (or a local .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str = "forest"
    postgres_password: SecretStr
    postgres_db: str = "forest"
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432

    # Path to the tesseract binary if it is not on PATH (e.g. on Windows).
    tesseract_cmd: str | None = None
    ocr_lang: str = "ukr"
    # Scanned pages with lower mean word confidence (0–100) are rejected as unreadable.
    ocr_min_confidence: float = 60.0

    # The Forest Archive files to load (not part of the repository).
    data_dir: Path = PROJECT_ROOT / "data"

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
