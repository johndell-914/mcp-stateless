"""The core claim — these three tests ARE the demo's thesis.

A cluster of N server instances (shared in-memory store, so app state is common —
isolating the *protocol* as the only variable) runs behind our deterministic proxy,
driven by a real ``mcp.Client`` over HTTP.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import socket
import threading
from collections.abc import AsyncIterator
from typing import Any

import uvicorn
from mcp import Client
from pydantic import SecretStr

from mcp_stateless_demo.config import Settings
from mcp_stateless_demo.proxy.app import ProxyState, create_proxy_app
from mcp_stateless_demo.server.app import build_app
from tests.conftest import MemoryCartStore


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _serve(app: Any) -> tuple[uvicorn.Server, str]:
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="critical"))
    threading.Thread(target=server.run, daemon=True).start()
    return server, f"http://127.0.0.1:{port}"


async def _wait(server: uvicorn.Server) -> None:
    for _ in range(250):
        if server.started:
            return
        await asyncio.sleep(0.02)
    raise RuntimeError("uvicorn did not start in time")


@contextlib.asynccontextmanager
async def cluster(
    *, stateless: bool, n: int = 2, sticky: bool = False
) -> AsyncIterator[tuple[str, ProxyState]]:
    store = MemoryCartStore()  # shared across instances = shared app state
    servers: list[uvicorn.Server] = []
    urls: list[str] = []
    for i in range(n):
        settings = Settings(
            token_secret=SecretStr("test-secret"),
            instance_id=f"inst-{i}",
            stateless_mode=stateless,
            database_url=SecretStr(""),
        )
        srv, url = _serve(build_app(settings, store))
        servers.append(srv)
        urls.append(url)
    for srv in servers:
        await _wait(srv)

    state = ProxyState(urls, sticky=sticky)
    proxy_srv, proxy_url = _serve(create_proxy_app(state))
    await _wait(proxy_srv)
    try:
        yield f"{proxy_url}/mcp", state
    finally:
        for srv in [*servers, proxy_srv]:
            srv.should_exit = True
        await asyncio.sleep(0.1)


def _payload(result: Any) -> dict[str, Any]:
    return json.loads(result.content[0].text)


async def test_stateless_roundrobin_works() -> None:
    """AFTER: any instance serves any request; the cart is consistent regardless."""
    async with cluster(stateless=True) as (url, state):
        async with Client(url, mode="auto") as client:
            token = _payload(await client.call_tool("create_cart", {}))["cart_token"]
            await client.call_tool("add_item", {"cart_token": token, "name": "apple", "qty": 2})
            await client.call_tool("add_item", {"cart_token": token, "name": "banana"})
            cart = _payload(await client.call_tool("get_cart", {"cart_token": token}))

    assert [(i["name"], i["qty"]) for i in cart["items"]] == [("apple", 2), ("banana", 1)]
    served = {e["instance"] for e in state.log}
    assert len(served) >= 2, f"expected requests spread across instances, got {served}"


async def test_legacy_roundrobin_fails() -> None:
    """BEFORE: the protocol session is stranded on one instance -> round-robin breaks it."""
    failed = False
    async with cluster(stateless=False) as (url, _state):
        try:
            async with Client(url, mode="legacy") as client:
                for _ in range(3):
                    result = await client.call_tool("create_cart", {})
                    if result.is_error:
                        failed = True
        except Exception:
            failed = True
    assert failed, "legacy protocol behind a plain round-robin LB must fail"


async def test_sticky_recovers_legacy() -> None:
    """THE TAX: sticky affinity pins the session back to its instance -> legacy works."""
    async with cluster(stateless=False, sticky=True) as (url, _state):
        async with Client(url, mode="legacy") as client:
            create = await client.call_tool("create_cart", {})
            assert not create.is_error
            token = _payload(create)["cart_token"]
            added = await client.call_tool("add_item", {"cart_token": token, "name": "apple"})
            assert not added.is_error
            cart = _payload(await client.call_tool("get_cart", {"cart_token": token}))
    assert [i["name"] for i in cart["items"]] == ["apple"]
