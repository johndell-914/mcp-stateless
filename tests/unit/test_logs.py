"""The log-query cutoff — scoping each beat's panel to its own start time is what makes the
per-beat instance counts truthful (sticky = 1, stateless = 2) instead of contaminated by
earlier steps.
"""

from __future__ import annotations

from datetime import UTC, datetime

from mcp_stateless_demo.cloud.logs import _cutoff_iso


def test_cutoff_scopes_to_since_with_microsecond_precision() -> None:
    # A beat records its start; the query must lower-bound at exactly that instant (µs) so a
    # request from the *previous* step in the same second is excluded.
    since = datetime(2026, 7, 20, 18, 20, 5, 700000, tzinfo=UTC)
    assert _cutoff_iso(since, minutes=6) == "2026-07-20T18:20:05.700000Z"


def test_cutoff_without_since_uses_a_rolling_window() -> None:
    iso = _cutoff_iso(None, minutes=6)
    assert iso.endswith("Z") and "T" in iso and "." not in iso  # second precision, no µs
