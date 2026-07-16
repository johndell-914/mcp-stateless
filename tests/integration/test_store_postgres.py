"""Live Supabase test — the phase-2 gate. Skipped automatically if DATABASE_URL is unset."""

import uuid

import pytest

from mcp_stateless_demo.cart.models import CartItem
from mcp_stateless_demo.cart.store import CartNotFound
from mcp_stateless_demo.cart.store_postgres import PostgresCartStore
from mcp_stateless_demo.config import get_settings

_settings = get_settings()
pytestmark = pytest.mark.skipif(
    not _settings.database_url.get_secret_value(),
    reason="DATABASE_URL not set - skipping live Supabase test",
)


async def test_live_create_add_get() -> None:
    store = await PostgresCartStore.connect(_settings.database_url.get_secret_value())
    try:
        cart_id = await store.create()
        assert (await store.get(cart_id)).items == []
        await store.add_item(cart_id, CartItem(name="apple", qty=2))
        await store.add_item(cart_id, CartItem(name="banana"))
        cart = await store.get(cart_id)
        assert [(i.name, i.qty) for i in cart.items] == [("apple", 2), ("banana", 1)]
    finally:
        await store.close()


async def test_live_unknown_cart_raises() -> None:
    store = await PostgresCartStore.connect(_settings.database_url.get_secret_value())
    try:
        with pytest.raises(CartNotFound):
            await store.get(str(uuid.uuid4()))
    finally:
        await store.close()
