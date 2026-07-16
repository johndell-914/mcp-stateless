"""ActRunner — drives a scripted cart act through the proxy and returns structured rows.

Pure logic, no UI, no printing. The CLI and the Gradio app are thin adapters over this.
The demo's two acts differ only in ``mode`` ("legacy" vs "auto"); everything the audience
sees (red rows / green rows / which instance served each call) comes from ``RowResult``.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp import Client
from pydantic import BaseModel

DEFAULT_ITEMS: list[tuple[str, int]] = [("apple", 2), ("banana", 1)]


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
        items = items if items is not None else DEFAULT_ITEMS
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
        instances = sorted({inst for success, inst in results if success and inst is not None})
        return BlastResult(total=total, ok=ok, instances=instances)
