"""Application settings. An empty database URL explicitly selects fixture mode."""

import re
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="STOCKSIGHT_",
        env_file=Path(__file__).resolve().parents[1] / ".env",
        extra="ignore",
    )

    app_name: str = "stocksight-api"

    database_url: SecretStr | None = None
    migration_database_url: SecretStr | None = None
    auth0_domain: str | None = None
    auth0_audience: str | None = None
    app_origin: str = "http://127.0.0.1:5173"
    session_max_age_seconds: int = Field(default=28800, ge=300, le=86400)

    @field_validator("app_origin")
    @classmethod
    def valid_app_origin(cls, value):
        value = value.rstrip("/")
        parts = urlsplit(value)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.path
            or parts.query
            or parts.fragment
            or (
                parts.scheme == "http"
                and parts.hostname not in {"localhost", "127.0.0.1", "::1"}
            )
        ):
            raise ValueError("Use an exact HTTPS frontend origin; HTTP is local-only")
        return value

    @field_validator("auth0_domain", "auth0_audience", mode="before")
    @classmethod
    def empty_auth_setting(cls, value):
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("auth0_domain")
    @classmethod
    def valid_auth_domain(cls, value):
        if value is not None and (
            len(value) > 253
            or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", value)
            or "." not in value
            or any(not part or len(part) > 63 for part in value.split("."))
        ):
            raise ValueError("Use an Auth0 hostname without a scheme, path or port")
        return value

    @field_validator("database_url", "migration_database_url", mode="before")
    @classmethod
    def empty_database_url(cls, value):
        return None if value == "" else value
