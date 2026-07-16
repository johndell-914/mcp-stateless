"""Typed configuration — the single source of truth for environment values.

Every module receives a ``Settings`` rather than reading ``os.environ`` directly.
Fields are added as later build phases need them; phase 2 needs only the DB URL,
the token secret, and the per-instance identity/mode.
"""

from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: SecretStr = SecretStr("")
    token_secret: SecretStr = SecretStr("")
    instance_id: str = "server"
    stateless_mode: bool = True


def get_settings() -> Settings:
    """Load settings from the environment / ``.env``."""
    return Settings()
