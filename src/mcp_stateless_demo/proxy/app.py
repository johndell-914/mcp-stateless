"""Deterministic reverse proxy in front of N server instances.

Two routing modes, both visible in the demo:

- **round-robin** (the plain LB): each request goes to the next instance. Under the
  legacy protocol this strands the session and every follow-up request lands on an
  instance that never saw the ``initialize`` -> "Session not found".
- **sticky** (the workaround / "tax"): the proxy *learns* which instance minted each
  ``mcp-session-id`` (from the initialize response) and pins that session's later
  requests back to it. Legacy works again -- at the cost of tracking sessions in the
  gateway and losing free horizontal scaling.

MCP-agnostic: it forwards bytes and reads one header. It is deterministic on purpose,
so the Act-1 failure can never be hidden by warm-instance routing.
"""

from __future__ import annotations

import itertools
from typing import Any

import httpx2
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

SESSION_HEADER = "mcp-session-id"
_REQ_DROP = {"host", "content-length"}
_RESP_DROP = {"content-length", "transfer-encoding"}


class ProxyState:
    def __init__(self, upstreams: list[str], *, sticky: bool = False) -> None:
        self.upstreams = list(upstreams)
        self.sticky = sticky
        self._counter = itertools.count()
        self.affinity: dict[str, int] = {}
        self.log: list[dict[str, Any]] = []

    def pick(self, session_id: str | None) -> int:
        if self.sticky and session_id and session_id in self.affinity:
            return self.affinity[session_id]
        return next(self._counter) % len(self.upstreams)


def create_proxy_app(state: ProxyState) -> Starlette:
    async def forward(request: Request) -> Response:
        session_id = request.headers.get(SESSION_HEADER)
        idx = state.pick(session_id)
        target = state.upstreams[idx]

        body = await request.body()
        headers = {k: v for k, v in request.headers.items() if k.lower() not in _REQ_DROP}
        url = target + request.url.path
        if request.url.query:
            url = f"{url}?{request.url.query}"

        async with httpx2.AsyncClient(timeout=30) as client:
            upstream = await client.request(request.method, url, content=body, headers=headers)

        # Learn session -> instance affinity from the initialize response.
        minted = upstream.headers.get(SESSION_HEADER)
        if state.sticky and minted:
            state.affinity[minted] = idx

        state.log.append(
            {
                "n": len(state.log) + 1,
                "method": request.method,
                "instance": idx,
                "had_session": bool(session_id),
                "status": upstream.status_code,
            }
        )
        out = {k: v for k, v in upstream.headers.items() if k.lower() not in _RESP_DROP}
        return Response(content=upstream.content, status_code=upstream.status_code, headers=out)

    async def health(_: Request) -> Response:
        return JSONResponse({"ok": True})

    async def log(_: Request) -> Response:
        return JSONResponse(
            {"upstreams": state.upstreams, "sticky": state.sticky, "log": state.log}
        )

    async def config(request: Request) -> Response:
        data = await request.json()
        if "sticky" in data:
            state.sticky = bool(data["sticky"])
        return JSONResponse({"sticky": state.sticky})

    async def target(request: Request) -> Response:
        data = await request.json()
        if "upstreams" in data:
            state.upstreams = list(data["upstreams"])
            state.affinity.clear()
        return JSONResponse({"upstreams": state.upstreams})

    return Starlette(
        routes=[
            Route("/health", health),
            Route("/log", log),
            Route("/config", config, methods=["POST"]),
            Route("/target", target, methods=["POST"]),
            Route("/mcp", forward, methods=["GET", "POST", "DELETE"]),
            Route("/mcp/{rest:path}", forward, methods=["GET", "POST", "DELETE"]),
        ]
    )
