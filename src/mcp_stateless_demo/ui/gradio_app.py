"""The Gradio demo app — a guided, four-beat narrative.

Thin orchestration over the ActRunner (drives the cart acts + the recycle drop + the
autoscale blast) and the proxy control endpoints (sticky / target / kill). Every visual
comes from ``panels``; this module wires buttons to handlers and pulls real Cloud Run logs
for the proof panels.

Beats:
  ① Scale it        round-robin, no sticky → "Session not found" (the break)
  ② The tax         sticky routing + session store → works, but costly
     💥 Recycle      hold a session, recycle its pod → drops mid-task
  ③ Go stateless    the 2-line change → works across instances, nothing to own
  ④ Prove at scale  blast the real autoscaling service → N instances, all green, proven by logs
"""

from __future__ import annotations

import asyncio
import os

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")  # NDA: no phone-home
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from typing import Any

import gradio as gr
import httpx2

from ..client.runner import ActResult, ActRunner, Conversation
from ..cloud.logs import LogProof, read_recent
from ..config import Settings, get_settings
from . import panels


class Demo:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self.legacy = settings.legacy_list() or ["http://127.0.0.1:9101", "http://127.0.0.1:9102"]
        self.modern = settings.modern_list() or ["http://127.0.0.1:9201", "http://127.0.0.1:9202"]
        self.runner = ActRunner(settings.mcp_url)
        self.scale_runner = ActRunner(settings.scale_mcp_url)
        self.legacy_svc = settings.legacy_service_list()
        self.scale_svc = settings.scale_service
        self.project = settings.gcp_project_or_none
        self._log_ctx: tuple[list[str], str, str, str | None] | None = None
        # The live agent session held across clicks (② / ③ start it, Recycle continues it).
        # Client-side plumbing that models "one agent, one session" — see runner.Conversation.
        self._conv: Conversation | None = None

    # ── proxy control ──────────────────────────────────────────────────────────────────
    async def _post(self, path: str, payload: dict[str, Any]) -> None:
        async with httpx2.AsyncClient(timeout=20) as client:
            await client.post(self.s.proxy_base.rstrip("/") + path, json=payload)

    async def _revive_all(self) -> None:
        for i in range(len(self.legacy)):
            await self._post("/revive", {"instance": i})

    # ── the live agent session (held across clicks) ─────────────────────────────────────
    async def _close_conversation(self) -> None:
        if self._conv is not None:
            await self._conv.close()
            self._conv = None

    async def _start_conversation(self, mode: str) -> ActResult:
        """Close any prior session and start a fresh live one in ``mode``, running a full act."""
        await self._close_conversation()
        self._conv = self.runner.conversation(mode)
        return await self._conv.scripted_act()

    def _legacy_index(self, name: str | None) -> int | None:
        for i, url in enumerate(self.legacy):
            if name and name in url:
                return i
        return None

    def _modern_index(self, name: str | None) -> int | None:
        for i, url in enumerate(self.modern):
            if name and name in url:
                return i
        return None

    # ── real-log proof (with ingestion-lag retry) ──────────────────────────────────────
    async def _pull_logs(
        self,
        services: list[str],
        *,
        headline: str,
        subtitle: str,
        contains: str | None,
        retries: int = 4,
        delay: float = 3.0,
    ) -> str:
        # Remember the last real-log context so the "Refresh logs" button can re-pull it
        # (Cloud Logging ingestion can lag past the initial retry window).
        self._log_ctx = (services, headline, subtitle, contains)
        if not services:
            return panels.render_log_proof(None, headline=headline, subtitle=subtitle)
        best: LogProof | None = None
        for attempt in range(retries):
            proofs = await asyncio.gather(
                *[
                    read_recent(s, project=self.project, minutes=6, limit=300, contains=contains)
                    for s in services
                ]
            )
            best = _merge(proofs, services[0])
            if best.ok and best.instances:
                break
            if attempt < retries - 1:
                await asyncio.sleep(delay)
        return panels.render_log_proof(best, headline=headline, subtitle=subtitle)

    async def refresh_logs(self) -> str:
        """Re-pull the most recent real-log context on demand (ingestion-lag catch-up)."""
        ctx = getattr(self, "_log_ctx", None)
        if not ctx:
            return panels.render_log_proof(
                None, headline="Cloud Run logs", subtitle="run a step first, then refresh"
            )
        services, headline, subtitle, contains = ctx
        return await self._pull_logs(
            services, headline=headline, subtitle=subtitle, contains=contains, retries=1
        )

    # ── beats ──────────────────────────────────────────────────────────────────────────
    async def intro(self) -> tuple[str, str, str, str, str]:
        await self._close_conversation()
        return (
            panels.render_stepper(0),
            panels.render_narrative("intro"),
            panels.render_architecture("before", self.legacy_names()),
            "",
            panels.render_log_proof(None, headline="Cloud Run logs"),
        )

    def legacy_names(self) -> list[str]:
        # Display names = the servers' own INSTANCE_IDs (legacy-a, legacy-b), inferred from URLs.
        return [_svc_short(u) for u in self.legacy]

    async def beat1_scale(self) -> tuple[str, str, str, str, str]:
        await self._close_conversation()  # the naive break is a one-shot; no live session to hold
        await self._post("/target", {"upstreams": self.legacy})
        await self._post("/config", {"sticky": False})
        await self._revive_all()
        result = await self.runner.run_act("legacy")
        logs = await self._pull_logs(
            self.legacy_svc,
            headline="Cloud Run logs — legacy instances",
            subtitle="the misrouted calls hit an instance that never saw the session",
            contains="POST /mcp",
        )
        return (
            panels.render_stepper(1),
            panels.render_narrative("scale"),
            panels.render_architecture("before", self.legacy_names(), served=result.instances),
            panels.render_results_table(result),
            logs,
        )

    async def beat2_sticky(self) -> tuple[str, str, str, str, str]:
        await self._post("/target", {"upstreams": self.legacy})
        await self._post("/config", {"sticky": True})
        await self._revive_all()
        result = await self._start_conversation("legacy")  # a live session, pinned by sticky
        return (
            panels.render_stepper(2),
            panels.render_narrative("sticky"),
            panels.render_architecture(
                "before", self.legacy_names(), sticky=True, store=True, served=result.instances
            ),
            panels.render_results_table(result),
            panels.render_log_proof(
                None,
                headline="sticky pins the session",
                subtitle="every call from this session lands on the same instance — "
                "see “served by” above. The cost is the gateway + store you now run.",
            ),
        )

    async def recycle_pod(self) -> tuple[str, str, str, str, str]:
        """Recycle the pod holding the live agent session, then continue on the SAME session.

        The outcome is whatever the architecture actually does — no fabricated session, no
        world-guessing. We act on the real conversation ② or ③ established: legacy pinned it to
        one pod, so recycling that pod drops it; stateless bound it to no pod, so a surviving
        instance carries on. Same disruptive action, the protocol decides the outcome.
        """
        conv = self._conv
        if conv is None or conv.pinned is None:
            return self._recycle_needs_session()

        pod = conv.pinned
        legacy = conv.mode == "legacy"
        idx = self._legacy_index(pod) if legacy else self._modern_index(pod)
        if idx is not None:
            await self._post("/kill", {"instance": idx})  # recycle the pod the session lives on

        result = await conv.continue_act()  # one more turn on the SAME held session
        if legacy:
            for r in result.rows:  # restate the generic client error as the true, known cause
                if not r.ok:
                    r.error = f"session lost — pod {pod} was recycled"
        served = [r.served_by for r in result.rows if r.ok and r.served_by]

        await self._revive_all()  # restore the proxy for a re-runnable demo
        if legacy:
            await self._close_conversation()  # the dropped session is dead — ② restarts a fresh one
            return (
                panels.render_stepper(2),
                panels.render_narrative("recycle"),
                panels.render_architecture(
                    "before", self.legacy_names(), sticky=True, store=True,
                    served=served, down=[pod],
                ),
                panels.render_results_table(result),
                panels.render_log_proof(
                    None,
                    headline="the pinned pod is gone",
                    subtitle="its live session went with it — the same conversation now fails",
                ),
            )
        return (
            panels.render_stepper(3),
            panels.render_narrative("recycle_survive"),
            panels.render_architecture("after", self.modern_names(), served=served, down=[pod]),
            panels.render_results_table(result),
            panels.render_log_proof(
                None,
                headline="the pod is gone — the agent isn't",
                subtitle="stateless: the cart rode in the token + Postgres, so a surviving "
                "instance served the rest",
            ),
        )

    def _recycle_needs_session(self) -> tuple[str, str, str, str, str]:
        return (
            panels.render_stepper(0),
            panels.render_narrative("recycle_none"),
            panels.render_architecture("before", self.legacy_names()),
            "",
            panels.render_log_proof(
                None,
                headline="no live session yet",
                subtitle="run ② Add the tax or ③ Go stateless first, then recycle its pod",
            ),
        )

    async def beat3_stateless(self) -> tuple[str, str, str, str, str]:
        await self._post("/target", {"upstreams": self.modern})
        await self._post("/config", {"sticky": False})
        await self._revive_all()
        result = await self._start_conversation("auto")  # a live session, bound to no pod
        return (
            panels.render_stepper(3),
            panels.render_narrative("stateless"),
            panels.render_architecture("after", self.modern_names(), served=result.instances),
            panels.render_results_table(result),
            panels.render_log_proof(
                None,
                headline="no gateway, no store",
                subtitle="the same cart is consistent across instances — state rides in the token",
            ),
        )

    def modern_names(self) -> list[str]:
        return [_svc_short(u) for u in self.modern]

    async def beat4_proof(self) -> tuple[str, str, str, str, str]:
        await self._close_conversation()
        result = await self.scale_runner.run_blast(60)
        served = result.instances
        logs = await self._pull_logs(
            [self.scale_svc],
            headline="Cloud Run logs — autoscaled service",
            subtitle="the platform's own instance ids — many, all serving, all green",
            contains="POST /mcp",
        )
        return (
            panels.render_stepper(4),
            panels.render_narrative("proof"),
            panels.render_architecture(
                "scale", served, served=served, scaling=True
            ),
            panels.render_blast_summary(result.ok, result.total, result.instances, result.counts),
            logs,
        )


def _svc_short(url: str) -> str:
    """A readable instance name from a Cloud Run URL or host:port (legacy-a, modern-b, …).

    ``https://mcp-stateless-legacy-a-123456789012.us-central1.run.app`` → ``legacy-a``;
    ``http://server-legacy-a:8000`` (docker) → ``server-legacy-a``.
    """
    host = url.split("//")[-1].split("/")[0].split(":")[0]
    sub = host.split(".")[0]  # subdomain only — drop the run.app / domain tail
    if sub.startswith("mcp-stateless-"):
        sub = sub[len("mcp-stateless-") :]
    parts = sub.split("-")
    if len(parts) > 1 and parts[-1].isdigit():  # strip a trailing -<projectnumber>
        parts = parts[:-1]
    return "-".join(parts)


def _merge(proofs: list[LogProof], service: str) -> LogProof:
    ok = any(p.ok for p in proofs)
    lines = [ln for p in proofs for ln in p.lines]
    lines.sort(key=lambda ln: ln.ts, reverse=True)
    instances = sorted({i for p in proofs for i in p.instances})
    err = next((p.error for p in proofs if not p.ok and p.error), None)
    return LogProof(ok=ok, service=service, lines=lines, instances=instances, error=err)


def build_demo(settings: Settings | None = None) -> gr.Blocks:
    d = Demo(settings or get_settings())
    with gr.Blocks(title="MCP goes stateless") as demo:
        gr.Markdown("# MCP is now stateless at the protocol layer")
        with gr.Row(equal_height=False):
            with gr.Column(scale=1, min_width=300):
                with gr.Group():
                    gr.Markdown("### Run the demo")
                    b1 = gr.Button("① Scale it", variant="primary")
                    b2 = gr.Button("② Add the tax (sticky + store)")
                    b3 = gr.Button("③ Go stateless", variant="primary")
                    b4 = gr.Button("④ Prove it at scale ⚡", variant="primary")
                    recycle = gr.Button("💥 Recycle a pod")
                    refresh = gr.Button("↻ Refresh logs")
                    reset = gr.Button("↺ Reset")
                narrative = gr.HTML(panels.render_narrative("intro"))  # what the current step does
            with gr.Column(scale=3):
                arch = gr.HTML(panels.render_architecture("before", d.legacy_names()))
                table = gr.HTML("")
                logproof = gr.HTML(panels.render_log_proof(None, headline="Cloud Run logs"))
        stepper = gr.HTML(visible=False)  # progress is conveyed by the numbered buttons now

        with gr.Accordion("What changed in the code — the whole migration", open=False):
            gr.HTML(panels.render_change_panel())

        gr.HTML(panels.render_brand_footer())

        outs = [stepper, narrative, arch, table, logproof]
        b1.click(d.beat1_scale, outputs=outs)
        b2.click(d.beat2_sticky, outputs=outs)
        recycle.click(d.recycle_pod, outputs=outs)
        b3.click(d.beat3_stateless, outputs=outs)
        b4.click(d.beat4_proof, outputs=outs)
        refresh.click(d.refresh_logs, outputs=[logproof])
        reset.click(d.intro, outputs=outs)
    return demo
