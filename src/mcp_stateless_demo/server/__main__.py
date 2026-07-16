"""Run a server instance: ``python -m mcp_stateless_demo.server``."""

from __future__ import annotations

import asyncio

import uvicorn

from ..cart.store_postgres import PostgresCartStore
from ..config import get_settings
from .app import build_app


async def _run() -> None:
    settings = get_settings()
    store = await PostgresCartStore.connect(settings.database_url.get_secret_value())
    app = build_app(settings, store)
    server = uvicorn.Server(
        uvicorn.Config(app, host="0.0.0.0", port=settings.port, log_level="info")
    )
    print(
        f"[server] instance={settings.instance_id} "
        f"stateless={settings.stateless_mode} port={settings.port}"
    )
    try:
        await server.serve()
    finally:
        await store.close()


if __name__ == "__main__":
    asyncio.run(_run())
