from __future__ import annotations

import uuid

import pytest

from mcp_stateless_demo.cart.models import Cart, CartItem
from mcp_stateless_demo.cart.store import CartNotFound


class MemoryCartStore:
    """Test-only in-memory CartStore fake (the product store is Postgres)."""

    def __init__(self) -> None:
        self._carts: dict[str, list[CartItem]] = {}

    async def create(self) -> str:
        cart_id = str(uuid.uuid4())
        self._carts[cart_id] = []
        return cart_id

    async def add_item(self, cart_id: str, item: CartItem) -> Cart:
        if cart_id not in self._carts:
            raise CartNotFound(cart_id)
        self._carts[cart_id].append(item)
        return Cart(id=cart_id, items=list(self._carts[cart_id]))

    async def get(self, cart_id: str) -> Cart:
        if cart_id not in self._carts:
            raise CartNotFound(cart_id)
        return Cart(id=cart_id, items=list(self._carts[cart_id]))


@pytest.fixture
def memory_store() -> MemoryCartStore:
    return MemoryCartStore()
