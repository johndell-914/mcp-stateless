"""The storage contract the rest of the app depends on (dependency inversion)."""

from __future__ import annotations

from typing import Protocol

from .models import Cart, CartItem


class CartNotFound(Exception):
    """A cart id did not resolve to a stored cart."""


class CartStore(Protocol):
    async def create(self) -> str:
        """Create an empty cart and return its id."""
        ...

    async def add_item(self, cart_id: str, item: CartItem) -> Cart:
        """Append ``item`` to the cart; raise ``CartNotFound`` if it is unknown."""
        ...

    async def get(self, cart_id: str) -> Cart:
        """Return the cart; raise ``CartNotFound`` if it is unknown."""
        ...
