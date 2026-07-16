"""The proxy control endpoints the UI drives — exercised in-process via ASGI (no socket)."""

from __future__ import annotations

import httpx2

from mcp_stateless_demo.proxy.app import ProxyState, create_proxy_app


async def test_control_endpoints() -> None:
    state = ProxyState(["http://a", "http://b"], sticky=False)
    transport = httpx2.ASGITransport(app=create_proxy_app(state))
    async with httpx2.AsyncClient(transport=transport, base_url="http://proxy") as client:
        assert (await client.get("/health")).json()["ok"] is True

        assert (await client.post("/config", json={"sticky": True})).json()["sticky"] is True
        assert state.sticky is True

        assert (await client.post("/kill", json={"instance": 0})).json()["down"] == [0]
        assert 0 in state.down

        await client.post("/revive", json={"instance": 0})
        assert 0 not in state.down

        await client.post("/target", json={"upstreams": ["http://x"]})
        assert state.upstreams == ["http://x"]

        body = (await client.get("/log")).json()
        assert set(body) >= {"upstreams", "sticky", "down", "log"}
