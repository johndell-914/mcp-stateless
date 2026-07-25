"""The 'At Scale' blast — fan-out proof AND real shopping activity.

The scale beat fires N independent stateless agents at the proxy. Each one now creates a cart
*and* adds an item, so the carts it writes carry real contents (not empty ``[]``) — while the
instance tally still proves Cloud Run–style fan-out across instances.
"""

from __future__ import annotations

from mcp_stateless_demo.client.runner import ActRunner
from tests.integration.test_core_claim import cluster_with_store


async def test_blast_populates_each_cart_and_fans_out() -> None:
    async with cluster_with_store(stateless=True, n=3) as (url, _state, store):
        result = await ActRunner(url).run_blast(total=6)

    assert result.ok == 6, "every stateless agent completes its create + add"
    assert result.total == 6

    carts = list(store._carts.values())
    assert len(carts) == 6, "the blast created one cart per agent"
    assert all(len(items) == 1 for items in carts), "each cart carries exactly one added item"

    assert len(result.instances) >= 2, "the blast fanned out across multiple instances"
    assert sum(c for _, c in result.counts) == 6, "the per-instance tally sums to the cart count"
