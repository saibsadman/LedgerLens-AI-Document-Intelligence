from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LedgerLens Document Intelligence"
    app_env: str = "development"
    secret_key: str = "development-only-change-me"
    api_key: str | None = None
    database_url: str = "sqlite:///./data/docintel.sqlite3"
    redis_url: str = "redis://localhost:6379/0"
    storage_path: Path = Path("./data/uploads")
    max_upload_mb: int = 100
    allowed_origins: list[str] | str = ["http://localhost:5173"]
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    use_celery: bool = False
    ocr_lang: str = "eng"
    tesseract_cmd: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    if settings.database_url.startswith("sqlite"):
        Path("./data").mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
