"""Log-proof model + graceful degradation (the live GCP read is exercised in integration)."""

from __future__ import annotations

import asyncio

from mcp_stateless_demo.cloud.logs import LogLine, LogProof, read_recent


def test_instance_count_counts_distinct() -> None:
    proof = LogProof(
        ok=True,
        service="svc",
        lines=[LogLine(ts="00:00:01", instance="aaa", text="x")],
        instances=["aaa", "bbb", "ccc"],
    )
    assert proof.instance_count == 3


def test_read_recent_never_raises() -> None:
    # Whatever the environment (bogus project, missing creds), the reader returns a
    # LogProof rather than raising — so the panel shows a fallback, never crashes the demo.
    proof = asyncio.run(read_recent("nonexistent", project="broken-project", minutes=1, limit=1))
    assert isinstance(proof, LogProof)
    assert proof.service == "nonexistent"
    assert proof.ok in (True, False)
