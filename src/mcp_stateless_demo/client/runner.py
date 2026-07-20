"""ActRunner — drives a scripted cart act through the proxy and returns structured rows.

Pure logic, no UI, no printing. The CLI and the Gradio app are thin adapters over this.
The demo's two acts differ only in ``mode`` ("legacy" vs "auto"); everything the audience
sees (red rows / green rows / which instance served each call) comes from ``RowResult``.
"""

from __future__ import annotations

import asyncio
import json
import random
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


async def _call(
    client: Client, n: int, tool: str, args: dict[str, Any]
) -> tuple[RowResult, dict[str, Any] | None]:
    """Call one MCP tool, mapping success/failure to a truthful RowResult (+ its raw payload)."""
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


class ActRunner:
    def __init__(self, proxy_url: str) -> None:
        self.proxy_url = proxy_url

    async def run_act(self, mode: str, items: list[tuple[str, int]] | None = None) -> ActResult:
        items = items if items is not None else _random_items()
        rows: list[RowResult] = []
        token = ""
        try:
            async with Client(self.proxy_url, mode=mode) as client:
                create_row, payload = await _call(client, 1, "create_cart", {})
                rows.append(create_row)
                if payload is not None:
                    token = str(payload.get("cart_token", ""))
                n = 1
                for name, qty in items:
                    n += 1
                    row, _ = await _call(
                        client, n, "add_item", {"cart_token": token, "name": name, "qty": qty}
                    )
                    rows.append(row)
                n += 1
                row, _ = await _call(client, n, "get_cart", {"cart_token": token})
                rows.append(row)
        except Exception as exc:  # noqa: BLE001 — a handshake failure is still a demo outcome
            if not rows:
                rows.append(
                    RowResult(n=1, tool="connect", ok=False, error=f"{type(exc).__name__}: {exc}")
                )
        return ActResult(mode=mode, rows=rows)

    def conversation(self, mode: str) -> Conversation:
        """A persistent, held-open agent session for the recycle beat (see ``Conversation``)."""
        return Conversation(self.proxy_url, mode)

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


class Conversation:
    """One live agent session, held open on a dedicated worker task across UI interactions.

    This models what a real agent does: hold ONE ``mcp.Client`` across many tool calls in a
    conversation. Under the legacy protocol that session is bound to one pod (sticky affinity),
    so recycling that pod truly drops it; under the stateless protocol it is bound to no pod, so
    recycling anything is a non-event. Keeping the client alive across separate UI clicks — not a
    fresh client per click — is what makes the recycle beat faithful instead of fabricated.

    It is **client-side demo plumbing, not part of the demonstrated architecture** — it never
    appears in the diagram or the story. Why a worker task rather than storing the client on the
    Demo: ``Client.__aenter__`` enters an anyio task group whose cancel scope must be exited in
    the *same* task, and Gradio dispatches each click on its own task. So a single worker task
    owns the client's whole lifecycle (enter, every tool call, exit); callers submit commands
    over a queue and await a future.
    """

    def __init__(self, proxy_url: str, mode: str) -> None:
        self.proxy_url = proxy_url
        self.mode = mode
        self.cart_token: str = ""
        self.pinned: str | None = None  # served_by of create_cart — the pod the session lives on
        self.rows: list[RowResult] = []
        self._n = 0
        self._queue: asyncio.Queue[
            tuple[str, dict[str, Any], asyncio.Future[RowResult | None]]
        ] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None

    async def _worker(self, started: asyncio.Future[None]) -> None:
        try:
            async with Client(self.proxy_url, mode=self.mode) as client:
                if not started.done():
                    started.set_result(None)
                while True:
                    op, args, fut = await self._queue.get()
                    if op == "close":
                        if not fut.done():
                            fut.set_result(None)
                        return
                    try:
                        fut.set_result(await self._exec(client, op, args))
                    except Exception as exc:  # noqa: BLE001 — surface per-call failures to caller
                        if not fut.done():
                            fut.set_exception(exc)
        except Exception as exc:  # noqa: BLE001 — a connect/handshake failure surfaces via _submit
            if not started.done():
                started.set_exception(exc)

    async def _exec(self, client: Client, op: str, args: dict[str, Any]) -> RowResult:
        self._n += 1
        n = self._n
        if op == "create":
            row, payload = await _call(client, n, "create_cart", {})
            if payload is not None:
                self.cart_token = str(payload.get("cart_token", ""))
            if row.ok:
                self.pinned = row.served_by  # the pod this session now lives on
            self.rows.append(row)
            return row
        if op == "add":
            row, _ = await _call(
                client,
                n,
                "add_item",
                {"cart_token": self.cart_token, "name": args["name"], "qty": args["qty"]},
            )
            self.rows.append(row)
            return row
        if op == "get":
            row, _ = await _call(client, n, "get_cart", {"cart_token": self.cart_token})
            self.rows.append(row)
            return row
        raise ValueError(f"unknown conversation op {op!r}")

    async def _submit(self, op: str, **args: Any) -> RowResult:
        if self._worker_task is None:
            started: asyncio.Future[None] = asyncio.get_running_loop().create_future()
            self._worker_task = asyncio.create_task(self._worker(started))
            await started  # raises if the client could not connect / initialize
        fut: asyncio.Future[RowResult | None] = asyncio.get_running_loop().create_future()
        await self._queue.put((op, args, fut))
        row = await fut
        assert row is not None  # only "close" resolves to None, and it never goes through _submit
        return row

    async def create(self) -> RowResult:
        return await self._submit("create")

    async def add(self, name: str, qty: int) -> RowResult:
        return await self._submit("add", name=name, qty=qty)

    async def get(self) -> RowResult:
        return await self._submit("get")

    async def scripted_act(self, items: list[tuple[str, int]] | None = None) -> ActResult:
        """A full little act on this session — create + a few adds + get. Rows accumulate."""
        items = items if items is not None else _random_items()
        await self.create()
        for name, qty in items:
            await self.add(name, qty)
        await self.get()
        return self.result()

    async def continue_act(self) -> ActResult:
        """One more add + get on the SAME session — used right after a recycle to show whether
        the session drops (legacy) or carries on (stateless). Picks an item not already in the
        cart so the post-recycle line reads distinctly (no confusing "avocado×3 … avocado×3")."""
        in_cart = {i["name"] for r in self.rows if r.cart for i in r.cart}
        pool = [n for n in _BASKET if n not in in_cart] or _BASKET
        await self.add(random.choice(pool), random.randint(1, 3))
        await self.get()
        return self.result()

    def result(self) -> ActResult:
        return ActResult(mode=self.mode, rows=list(self.rows))

    async def close(self) -> None:
        task = self._worker_task
        self._worker_task = None
        if task is None:
            return
        if not task.done():
            fut: asyncio.Future[RowResult | None] = asyncio.get_running_loop().create_future()
            await self._queue.put(("close", {}, fut))
        try:
            await asyncio.wait_for(task, timeout=10)
        except Exception:  # noqa: BLE001 — shutting a conversation down must never raise into UI
            pass
