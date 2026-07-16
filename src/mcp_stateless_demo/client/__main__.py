"""CLI act-runner (local fallback) driving a running proxy (``PROXY_URL``).

Usage: ``python -m mcp_stateless_demo.client [legacy|auto] [--blast N]``. For the
self-contained end-to-end check that spins up its own cluster, use ``scripts/smoke.py``.
"""

from __future__ import annotations

import argparse
import asyncio

from ..config import get_settings
from .runner import ActResult, ActRunner


def _print_act(result: ActResult) -> None:
    print(f"\n=== act: mode={result.mode} ===")
    for row in result.rows:
        status = "OK " if row.ok else "ERR"
        detail = f"served_by={row.served_by} cart={row.cart}" if row.ok else row.error
        print(f"  [{status}] #{row.n} {row.tool}: {detail}")
    print(f"  -> all_ok={result.all_ok} instances={result.instances}")


async def _main(mode: str, blast: int) -> None:
    settings = get_settings()
    proxy_url = settings.proxy_url or "http://127.0.0.1:9000/mcp"
    runner = ActRunner(proxy_url)
    if blast:
        result = await runner.run_blast(blast)
        print(f"blast: {result.ok}/{result.total} ok across instances {result.instances}")
    else:
        _print_act(await runner.run_act(mode))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", nargs="?", default="auto", choices=["legacy", "auto"])
    parser.add_argument("--blast", type=int, default=0)
    args = parser.parse_args()
    asyncio.run(_main(args.mode, args.blast))
