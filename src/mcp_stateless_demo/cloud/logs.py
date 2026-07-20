"""Pull real Cloud Run request logs so the UI can *prove* an event happened on real infra.

This is the credibility layer of beat 4: the live instance strip shows our own
``served_by`` names, and this shows the matching Cloud Run stdout lines (each tagged with
the platform's own ``instanceId``) — evidence the audience can trust because we didn't
generate it.

Design notes:
- The Google client is synchronous; ``read_recent`` wraps it in ``asyncio.to_thread`` so
  the Gradio event loop is never blocked.
- Everything degrades gracefully: no credentials (local Docker), missing library, or an API
  error returns ``ok=False`` with a message instead of raising, so the panel can show a
  friendly fallback rather than crashing the demo.
- Cloud Logging has a few-seconds ingestion lag (confirmed in the spike), so callers should
  poll/retry rather than expect lines the instant a burst finishes.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel


class LogLine(BaseModel):
    ts: str  # HH:MM:SS, UTC
    instance: str  # short Cloud Run instanceId — the *tail*, "" if absent
    text: str  # the log message (e.g. uvicorn's `POST /mcp HTTP/1.1 200 OK`)


class LogProof(BaseModel):
    ok: bool
    service: str
    lines: list[LogLine]
    instances: list[str]  # distinct short instanceIds seen, sorted
    error: str | None = None

    @property
    def instance_count(self) -> int:
        return len(self.instances)


def _cutoff_iso(since: datetime | None, minutes: int) -> str:
    """RFC3339 lower bound for the log query — the beat's start (``since``, with microsecond
    precision so a query can't pick up the *previous* step's tail), else a rolling ``minutes``
    window. Scoping each panel to ``since`` is what makes the per-beat instance counts truthful
    (sticky = 1 instance, stateless = 2) instead of contaminated by earlier steps.
    """
    dt = since if since is not None else (datetime.now(UTC) - timedelta(minutes=minutes))
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ" if since is not None else "%Y-%m-%dT%H:%M:%SZ")


def _read_sync(
    service: str,
    project: str | None,
    minutes: int,
    limit: int,
    contains: str | None,
    since: datetime | None,
) -> LogProof:
    try:
        from google.cloud import logging as gcloud_logging
    except Exception as exc:  # noqa: BLE001 — library absent → friendly fallback
        return LogProof(
            ok=False, service=service, lines=[], instances=[], error=f"logging lib: {exc}"
        )
    try:
        client = gcloud_logging.Client(project=project) if project else gcloud_logging.Client()
        cutoff = _cutoff_iso(since, minutes)
        filter_ = (
            'resource.type="cloud_run_revision" '
            f'AND resource.labels.service_name="{service}" '
            'AND logName:"stdout" '
            f'AND timestamp>="{cutoff}"'
        )
        entries = client.list_entries(
            filter_=filter_, order_by=gcloud_logging.DESCENDING, max_results=limit
        )
        lines: list[LogLine] = []
        instances: set[str] = set()
        for entry in entries:
            payload = entry.payload
            text = payload if isinstance(payload, str) else str(payload)
            if contains and contains not in text:
                continue
            # Cloud Run instanceIds are ~156 chars sharing a common *prefix*; the tail is
            # the reliable per-instance distinguisher (even 12-char prefixes collide).
            full_iid = (entry.labels or {}).get("instanceId", "")
            iid = full_iid[-12:] if full_iid else ""
            ts = entry.timestamp.strftime("%H:%M:%S") if entry.timestamp else ""
            lines.append(LogLine(ts=ts, instance=iid, text=text))
            if iid:
                instances.add(iid)
        return LogProof(ok=True, service=service, lines=lines, instances=sorted(instances))
    except Exception as exc:  # noqa: BLE001 — any API/creds error → friendly fallback
        return LogProof(
            ok=False,
            service=service,
            lines=[],
            instances=[],
            error=f"{type(exc).__name__}: {exc}",
        )


async def read_recent(
    service: str,
    *,
    project: str | None = None,
    minutes: int = 5,
    limit: int = 120,
    contains: str | None = None,
    since: datetime | None = None,
) -> LogProof:
    """Recent Cloud Run stdout lines for ``service``, newest first.

    ``contains`` filters to lines with that substring (e.g. ``"POST /mcp"``). ``since`` scopes
    the query to a start time (a beat's start) so the panel shows only that beat's requests.
    Returns ``ok=False`` (never raises) if credentials or the API are unavailable.
    """
    return await asyncio.to_thread(_read_sync, service, project, minutes, limit, contains, since)
