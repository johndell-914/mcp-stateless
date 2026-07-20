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
    # When True, append a per-process boot id to the served_by name so the N instances of
    # one autoscaling Cloud Run service are distinguishable in the UI. Fixed single-instance
    # services leave this off and keep their clean name (legacy-a, modern-a, ...).
    append_boot_id: bool = False
    stateless_mode: bool = True
    port: int = 8000

    # proxy
    upstreams: str = ""
    sticky: bool = False

    # client / ui
    proxy_base: str = "http://127.0.0.1:9000"
    legacy_upstreams: str = ""
    modern_upstreams: str = ""
    ui_auth: str = ""

    # beat 4 — real Cloud Run autoscale target (hit directly, bypassing the proxy)
    scale_upstream: str = ""
    # Cloud Run service names for the live log-proof panel; gcp_project "" = auto-detect via ADC
    scale_service: str = "mcp-stateless-scale"
    proxy_service: str = "mcp-stateless-proxy"  # its logs show the 503s of a recycle drop
    legacy_services: str = ""
    modern_services: str = ""
    gcp_project: str = ""

    @staticmethod
    def _split(value: str) -> list[str]:
        return [u.strip() for u in value.split(",") if u.strip()]

    def upstream_list(self) -> list[str]:
        return self._split(self.upstreams)

    def legacy_list(self) -> list[str]:
        return self._split(self.legacy_upstreams)

    def modern_list(self) -> list[str]:
        return self._split(self.modern_upstreams)

    def legacy_service_list(self) -> list[str]:
        return self._split(self.legacy_services)

    def modern_service_list(self) -> list[str]:
        return self._split(self.modern_services)

    @property
    def mcp_url(self) -> str:
        return self.proxy_base.rstrip("/") + "/mcp"

    @property
    def scale_mcp_url(self) -> str:
        return self.scale_upstream.rstrip("/") + "/mcp"

    @property
    def gcp_project_or_none(self) -> str | None:
        return self.gcp_project or None


def get_settings() -> Settings:
    """Load settings from the environment / ``.env``."""
    return Settings()
