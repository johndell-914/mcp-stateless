"""ActRunner — drives a scripted cart act through the proxy and returns structured rows.

Pure logic, no UI, no printing. The CLI and the Gradio app are thin adapters over this.
The demo's two acts differ only in ``mode`` ("legacy" vs "auto"); everything the audience
sees (red rows / green rows / which instance served each call) comes from ``RowResult``.
"""

from __future__ import annotations

import asyncio
import json
import random
from collections.abc import Awaitable, Callable
from typing import Any

from mcp import Client
from pydantic import BaseModel

# A small basket so every act sends a *different* order — the point is that each button
# click is a fresh set of real MCP requests, not a canned replay of the same cart.
_BASKET: list[str] = [
    "apple", "banana", "cold brew", "oat milk", "sourdough", "avocado",
    "orange", "greek yogurt", "granola", "kombucha", "dark chocolate", "eggs",
]


def _random_items() -> list[tuple[str, int]]:
    names = random.sample(_BASKET, k=random.randint(2, 3))
    return [(n, random.randint(1, 3)) for n in names]


class RowResult(BaseModel):
    n: int
    tool: str
    ok: bool
    served_by: str | None = None
    cart: list[dict[str, Any]] | None = None
    error: str | None = None


class ActResult(BaseModel):
    mode: str
    rows: list[RowResult]

    @property
    def all_ok(self) -> bool:
        return len(self.rows) > 0 and all(r.ok for r in self.rows)

    @property
    def any_error(self) -> bool:
        return any(not r.ok for r in self.rows)

    @property
    def instances(self) -> list[str]:
        return sorted({r.served_by for r in self.rows if r.served_by is not None})


class BlastResult(BaseModel):
    total: int
    ok: int
    instances: list[str]
    counts: list[tuple[str, int]] = []  # (instance, requests handled), busiest first


def _result_text(result: Any) -> str:
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            return text
    return ""


class ActRunner:
    def __init__(self, proxy_url: str) -> None:
        self.proxy_url = proxy_url

    async def _call(
        self, client: Client, n: int, tool: str, args: dict[str, Any]
    ) -> tuple[RowResult, dict[str, Any] | None]:
        try:
            result = await client.call_tool(tool, args)
        except Exception as exc:  # noqa: BLE001 — capture any failure as a red row, truthfully
            return RowResult(n=n, tool=tool, ok=False, error=f"{type(exc).__name__}: {exc}"), None
        if result.is_error:
            return RowResult(n=n, tool=tool, ok=False, error=_result_text(result) or "error"), None
        payload: dict[str, Any] = json.loads(_result_text(result))
        row = RowResult(
            n=n, tool=tool, ok=True, served_by=payload.get("served_by"), cart=payload.get("items")
        )
        return row, payload

    async def run_act(self, mode: str, items: list[tuple[str, int]] | None = None) -> ActResult:
        items = items if items is not None else _random_items()
        rows: list[RowResult] = []
        token = ""
        try:
            async with Client(self.proxy_url, mode=mode) as client:
                create_row, payload = await self._call(client, 1, "create_cart", {})
                rows.append(create_row)
                if payload is not None:
                    token = str(payload.get("cart_token", ""))
                n = 1
                for name, qty in items:
                    n += 1
                    row, _ = await self._call(
                        client, n, "add_item", {"cart_token": token, "name": name, "qty": qty}
                    )
                    rows.append(row)
                n += 1
                row, _ = await self._call(client, n, "get_cart", {"cart_token": token})
                rows.append(row)
        except Exception as exc:  # noqa: BLE001 — a handshake failure is still a demo outcome
            if not rows:
                rows.append(
                    RowResult(n=1, tool="connect", ok=False, error=f"{type(exc).__name__}: {exc}")
                )
        return ActResult(mode=mode, rows=rows)

    async def run_recycle_drop(self, on_pin: Callable[[str], Awaitable[None]]) -> ActResult:
        """Honest 'sticky is fragile' demo: hold one legacy session, recycle its pinned pod
        mid-conversation, then keep going on the SAME session.

        With sticky routing the session lives on one instance. ``on_pin`` is called with that
        instance's name to recycle it; the next call on the held session then finds its pod
        gone and fails — the mid-task drop, shown for real (not faked). Runs as one act so no
        client state has to survive across UI clicks.
        """
        rows: list[RowResult] = []
        try:
            async with Client(self.proxy_url, mode="legacy") as client:
                (n1, q1), (n2, q2) = _random_items()[:2]
                r1, p1 = await self._call(client, 1, "create_cart", {})
                rows.append(r1)
                token = str(p1.get("cart_token", "")) if p1 else ""
                pinned = r1.served_by
                r2, _ = await self._call(
                    client, 2, "add_item", {"cart_token": token, "name": n1, "qty": q1}
                )
                rows.append(r2)
                # recycle the pod this session is pinned to, then continue the SAME session
                if pinned:
                    await on_pin(pinned)
                r3, _ = await self._call(
                    client, 3, "add_item", {"cart_token": token, "name": n2, "qty": q2}
                )
                rows.append(r3)
                r4, _ = await self._call(client, 4, "get_cart", {"cart_token": token})
                rows.append(r4)
                # The post-recycle failures are the pinned pod being gone; the MCP client only
                # surfaces a generic wrapper, so restate the true, known cause for the screen.
                for r in (r3, r4):
                    if not r.ok:
                        r.error = f"session lost — pod {pinned} was recycled"
        except Exception as exc:  # noqa: BLE001 — a mid-session drop is a valid demo outcome
            if not rows:
                rows.append(
                    RowResult(n=1, tool="connect", ok=False, error=f"{type(exc).__name__}: {exc}")
                )
        return ActResult(mode="legacy-recycle", rows=rows)

    async def run_blast(self, total: int = 50) -> BlastResult:
        async def one() -> tuple[bool, str | None]:
            try:
                async with Client(self.proxy_url, mode="auto") as client:
                    result = await client.call_tool("create_cart", {})
                    if result.is_error:
                        return False, None
                    payload: dict[str, Any] = json.loads(_result_text(result))
                    served: str | None = payload.get("served_by")
                    return True, served
            except Exception:  # noqa: BLE001
                return False, None

        results = await asyncio.gather(*[one() for _ in range(total)])
        ok = sum(1 for success, _ in results if success)
        tally: dict[str, int] = {}
        for success, inst in results:
            if success and inst is not None:
                tally[inst] = tally.get(inst, 0) + 1
        counts = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))
        instances = sorted(tally)
        return BlastResult(total=total, ok=ok, instances=instances, counts=counts)
