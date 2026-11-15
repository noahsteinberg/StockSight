"""Application settings. An empty database URL explicitly selects fixture mode."""

from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="STOCKSIGHT_",
        env_file=Path(__file__).resolve().parents[1] / ".env",
        extra="ignore",
    )

    app_name: str = "stocksight-api"

    database_url: SecretStr | None = None

    @field_validator("database_url", mode="before")
    @classmethod
    def empty_database_url(cls, value):
        return None if value == "" else value
