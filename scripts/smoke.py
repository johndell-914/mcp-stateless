"""smoke.py -- headless end-to-end: BEFORE all-red, AFTER all-green.

Spins up a 2-instance cluster + proxy in-process (Postgres/Supabase from .env), runs both
acts through the ActRunner, and asserts the demo's thesis. Exit 0 on success, 1 otherwise.

    uv run python scripts/smoke.py
"""

from __future__ import annotations

import asyncio
import socket
from typing import Any

import uvicorn

from mcp_stateless_demo.cart.store_postgres import PostgresCartStore
from mcp_stateless_demo.client.runner import ActResult, ActRunner
from mcp_stateless_demo.config import Settings, get_settings
from mcp_stateless_demo.proxy.app import ProxyState, create_proxy_app
from mcp_stateless_demo.server.app import build_app


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


async def _start(app: Any, port: int) -> uvicorn.Server:
    """Run a server as a task in THIS event loop, so the asyncpg pool shares the loop.

    (Threads with separate loops break asyncpg: "another operation is in progress".)
    """
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="critical"))
    server.install_signal_handlers = lambda: None
    asyncio.create_task(server.serve())
    for _ in range(250):
        if server.started:
            return server
        await asyncio.sleep(0.02)
    raise RuntimeError("uvicorn did not start")


async def _cluster_act(
    base: Settings, store: PostgresCartStore, *, stateless: bool, mode: str
) -> ActResult:
    servers: list[uvicorn.Server] = []
    urls: list[str] = []
    for i in range(2):
        settings = Settings(
            token_secret=base.token_secret,
            database_url=base.database_url,
            instance_id=f"inst-{i}",
            stateless_mode=stateless,
        )
        port = _free_port()
        servers.append(await _start(build_app(settings, store), port))
        urls.append(f"http://127.0.0.1:{port}")
    proxy_port = _free_port()
    servers.append(await _start(create_proxy_app(ProxyState(urls, sticky=False)), proxy_port))
    try:
        return await ActRunner(f"http://127.0.0.1:{proxy_port}/mcp").run_act(mode)
    finally:
        for srv in servers:
            srv.should_exit = True
        await asyncio.sleep(0.2)


def _print(result: ActResult) -> None:
    print(f"\n--- {result.mode} (instances touched: {result.instances or 'n/a'}) ---")
    for row in result.rows:
        mark = "GREEN" if row.ok else "RED  "
        detail = f"served_by={row.served_by} cart={row.cart}" if row.ok else row.error
        print(f"  [{mark}] #{row.n} {row.tool}: {detail}")


async def _main() -> int:
    base = get_settings()
    if not base.database_url.get_secret_value():
        print("DATABASE_URL not set - smoke needs Supabase (.env).")
        return 1

    store = await PostgresCartStore.connect(base.database_url.get_secret_value())
    try:
        before = await _cluster_act(base, store, stateless=False, mode="legacy")
        after = await _cluster_act(base, store, stateless=True, mode="auto")
    finally:
        await store.close()

    print("\n================ SMOKE ================")
    _print(before)
    _print(after)

    before_all_red = not any(r.ok for r in before.rows) and len(before.rows) > 0
    after_all_green = after.all_ok
    final_cart = after.rows[-1].cart if after.rows else None
    cart_ok = final_cart == [{"name": "apple", "qty": 2}, {"name": "banana", "qty": 1}]

    ok = before_all_red and after_all_green and cart_ok
    print("\n======================================")
    print(f"BEFORE all-red : {before_all_red}")
    print(f"AFTER all-green: {after_all_green}")
    print(f"AFTER cart ok  : {cart_ok}")
    print(f"RESULT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
