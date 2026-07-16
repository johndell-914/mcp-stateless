"""The only product ``CartStore`` — Postgres via asyncpg (Supabase).

App state lives here, addressed by a cart id. It survives instance churn, which
is exactly why the demo's failure in the "before" act cannot be blamed on the
app: the app already stores state correctly and durably; it is the *protocol*
session that dies on the wrong instance.
"""

from __future__ import annotations

import json
import ssl

import asyncpg

from .models import Cart, CartItem
from .store import CartNotFound


def _ssl_context() -> ssl.SSLContext:
    # TLS is required by Supabase. We require encryption but do not verify the
    # chain — the pooler's cert chain is awkward to verify cross-platform and this
    # is a demo. For stricter verification, load Supabase's CA cert here instead.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _row_to_cart(row: asyncpg.Record) -> Cart:
    raw = row["items"]
    items = json.loads(raw) if isinstance(raw, str) else raw
    return Cart(id=row["id"], items=[CartItem(**it) for it in items])


class PostgresCartStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @classmethod
    async def connect(cls, dsn: str, *, min_size: int = 1, max_size: int = 5) -> PostgresCartStore:
        pool = await asyncpg.create_pool(
            dsn, ssl=_ssl_context(), min_size=min_size, max_size=max_size
        )
        return cls(pool)

    async def close(self) -> None:
        await self._pool.close()

    async def create(self) -> str:
        row = await self._pool.fetchrow("insert into carts default values returning id::text")
        return str(row["id"])

    async def add_item(self, cart_id: str, item: CartItem) -> Cart:
        row = await self._pool.fetchrow(
            "update carts set items = items || $2::jsonb, updated_at = now() "
            "where id = $1::uuid returning id::text, items",
            cart_id,
            json.dumps([item.model_dump()]),
        )
        if row is None:
            raise CartNotFound(cart_id)
        return _row_to_cart(row)

    async def get(self, cart_id: str) -> Cart:
        row = await self._pool.fetchrow(
            "select id::text, items from carts where id = $1::uuid", cart_id
        )
        if row is None:
            raise CartNotFound(cart_id)
        return _row_to_cart(row)
