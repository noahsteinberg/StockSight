"""Application settings. No database or external service is required."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="STOCKSIGHT_",
        env_file=Path(__file__).resolve().parents[1] / ".env",
        extra="ignore",
    )

    app_name: str = "stocksight-api"
