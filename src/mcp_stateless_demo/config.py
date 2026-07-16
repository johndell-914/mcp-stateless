"""Typed configuration — the single source of truth for environment values.

Every module receives a ``Settings`` rather than reading ``os.environ`` directly.
"""

from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # domain / server
    database_url: SecretStr = SecretStr("")
    token_secret: SecretStr = SecretStr("")
    instance_id: str = "server"
    stateless_mode: bool = True
    port: int = 8000

    # proxy
    upstreams: str = ""
    sticky: bool = False

    def upstream_list(self) -> list[str]:
        return [u.strip() for u in self.upstreams.split(",") if u.strip()]


def get_settings() -> Settings:
    """Load settings from the environment / ``.env``."""
    return Settings()
