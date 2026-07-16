import uuid

import pytest

from mcp_stateless_demo.cart.models import CartItem
from mcp_stateless_demo.cart.store import CartNotFound
from tests.conftest import MemoryCartStore


async def test_create_then_empty(memory_store: MemoryCartStore) -> None:
    cart_id = await memory_store.create()
    cart = await memory_store.get(cart_id)
    assert cart.id == cart_id
    assert cart.items == []


async def test_add_items_ordered(memory_store: MemoryCartStore) -> None:
    cart_id = await memory_store.create()
    await memory_store.add_item(cart_id, CartItem(name="apple", qty=2))
    await memory_store.add_item(cart_id, CartItem(name="banana"))
    cart = await memory_store.get(cart_id)
    assert [(i.name, i.qty) for i in cart.items] == [("apple", 2), ("banana", 1)]


async def test_get_unknown_raises(memory_store: MemoryCartStore) -> None:
    with pytest.raises(CartNotFound):
        await memory_store.get(str(uuid.uuid4()))


async def test_add_to_unknown_raises(memory_store: MemoryCartStore) -> None:
    with pytest.raises(CartNotFound):
        await memory_store.add_item(str(uuid.uuid4()), CartItem(name="x"))
