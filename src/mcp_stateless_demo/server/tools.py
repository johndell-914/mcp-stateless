"""The three cart tools, registered over an injected store + token codec + instance id.

These are byte-identical across both acts (principle P1): what changes between
"before" and "after" is the server flag and the client mode, never these tools.
Each response stamps ``served_by`` so the UI can show which instance handled it.
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..cart.models import CartItem
from ..cart.store import CartStore
from ..cart.token import CartTokenCodec


def register_cart_tools(
    server: MCPServer,
    store: CartStore,
    codec: CartTokenCodec,
    instance_id: str,
) -> None:
    @server.tool()
    async def create_cart() -> dict[str, Any]:
        """Create a cart and return an opaque cart_token handle."""
        cart_id = await store.create()
        return {"served_by": instance_id, "cart_token": codec.encode(cart_id), "items": []}

    @server.tool()
    async def add_item(cart_token: str, name: str, qty: int = 1) -> dict[str, Any]:
        """Add an item to the cart identified by cart_token."""
        cart_id = codec.decode(cart_token)
        cart = await store.add_item(cart_id, CartItem(name=name, qty=qty))
        return {
            "served_by": instance_id,
            "cart_token": cart_token,
            "items": [i.model_dump() for i in cart.items],
        }

    @server.tool()
    async def get_cart(cart_token: str) -> dict[str, Any]:
        """Return the current contents of the cart identified by cart_token."""
        cart_id = codec.decode(cart_token)
        cart = await store.get(cart_id)
        return {
            "served_by": instance_id,
            "cart_token": cart_token,
            "items": [i.model_dump() for i in cart.items],
        }
