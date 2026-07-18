"""ActRunner over the cluster harness — the runner's structured output is correct per mode."""

from __future__ import annotations

from mcp_stateless_demo.client.runner import ActRunner
from tests.integration.test_core_claim import cluster


async def test_runner_stateless_all_green() -> None:
    # Pass explicit items so the assertion is deterministic (the demo default is random).
    async with cluster(stateless=True) as (url, _state):
        result = await ActRunner(url).run_act("auto", items=[("apple", 2), ("banana", 1)])
    assert result.all_ok
    assert result.rows[-1].cart == [{"name": "apple", "qty": 2}, {"name": "banana", "qty": 1}]


async def test_runner_legacy_all_red() -> None:
    async with cluster(stateless=False) as (url, _state):
        result = await ActRunner(url).run_act("legacy")
    assert result.any_error
    assert not any(row.ok for row in result.rows)
