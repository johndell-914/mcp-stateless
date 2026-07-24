"""The persistent Conversation — one held-open mcp.Client across calls.

These assert the recycle beat's fidelity at the level the UI actually uses: a *held* session
(not a fresh client per call). Legacy + recycle its pinned pod -> the session drops; stateless
+ recycle the pod that created the cart -> a surviving instance carries on. Same held session,
the protocol decides the outcome.
"""

from __future__ import annotations

from mcp_stateless_demo.client.runner import Conversation
from tests.integration.test_core_claim import cluster


async def test_conversation_stateless_survives_recycle() -> None:
    async with cluster(stateless=True, n=2) as (url, state):
        conv = Conversation(url, mode="auto")
        try:
            create = await conv.create()
            assert create.ok and conv.pinned is not None
            await conv.add("apple", 2)
            creator = conv.pinned
            state.down.add(int(creator.split("-")[-1]))  # recycle the pod that created the cart
            survived = await conv.add("banana", 1)  # continue the SAME held session
            snapshot = await conv.get()
        finally:
            await conv.close()

    assert survived.ok, "a held stateless session survives recycling its creator pod"
    assert survived.served_by != creator, "a different, surviving instance served the follow-up"
    assert [i["name"] for i in (snapshot.cart or [])] == ["apple", "banana"], "cart is intact"


async def test_conversation_legacy_drops_on_recycle() -> None:
    async with cluster(stateless=False, sticky=True, n=2) as (url, state):
        conv = Conversation(url, mode="legacy")
        try:
            create = await conv.create()
            assert create.ok and conv.pinned is not None
            await conv.add("apple", 1)
            pinned = conv.pinned
            state.down.add(int(pinned.split("-")[-1]))  # recycle the pod the session is pinned to
            dropped = await conv.add("banana", 1)  # the same held session now has no pod
        finally:
            await conv.close()

    assert not dropped.ok, "a held legacy session drops when its pinned pod is recycled"


async def test_conversation_close_is_idempotent() -> None:
    async with cluster(stateless=True, n=2) as (url, _state):
        conv = Conversation(url, mode="auto")
        await conv.create()
        await conv.close()
        await conv.close()  # second close is a no-op, must not raise


async def test_scale_break_succeeds_then_breaks_on_scale_out() -> None:
    # ① 'Scale it': create the cart while one instance is behind the LB (works), then scale out —
    # the same session's follow-ups round-robin and the ones on the new instance break.
    async with cluster(stateless=False, n=2) as (url, state):
        both = list(state.upstreams)
        state.upstreams = both[:1]  # phase 1: a single instance behind the LB

        async def scale_out() -> None:
            state.upstreams = both  # phase 2: add the second instance → round-robin

        conv = Conversation(url, mode="legacy")
        try:
            result = await conv.scale_break(scale_out)
        finally:
            await conv.close()

    rows = result.rows
    assert rows[0].tool == "create_cart" and rows[0].ok, "create must succeed on the one instance"
    assert any(not r.ok for r in rows[1:]), "a scaled-out follow-up must break (session not found)"


async def test_continue_act_adds_a_distinct_item() -> None:
    # The post-recycle turn must not re-add an item already in the cart (no "avocado … avocado").
    async with cluster(stateless=True, n=2) as (url, _state):
        conv = Conversation(url, mode="auto")
        try:
            await conv.scripted_act()
            snap = await conv.continue_act()
        finally:
            await conv.close()
    final = [i["name"] for i in (snap.rows[-1].cart or [])]
    assert len(final) == len(set(final)), f"duplicate line items in cart: {final}"
