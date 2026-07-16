"""The Gradio demo app.

Thin orchestration over the ActRunner (drives the acts) and the proxy control endpoints
(sticky / kill / target). All visuals come from ``panels``; this module just wires buttons
to handlers and returns HTML fragments.
"""

from __future__ import annotations

import os

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")  # NDA: no phone-home
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from typing import Any

import gradio as gr
import httpx2

from ..client.runner import ActRunner
from ..config import Settings, get_settings
from . import panels


def _names(n: int) -> list[str]:
    return [f"inst-{i}" for i in range(n)]


class Demo:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self.legacy = settings.legacy_list() or ["http://127.0.0.1:9101", "http://127.0.0.1:9102"]
        self.modern = settings.modern_list() or ["http://127.0.0.1:9201", "http://127.0.0.1:9202"]
        self.runner = ActRunner(settings.mcp_url)

    async def _post(self, path: str, payload: dict[str, Any]) -> None:
        async with httpx2.AsyncClient(timeout=15) as client:
            await client.post(self.s.proxy_base.rstrip("/") + path, json=payload)

    async def _down_names(self) -> list[str]:
        async with httpx2.AsyncClient(timeout=15) as client:
            resp = await client.get(self.s.proxy_base.rstrip("/") + "/log")
        names = _names(len(self.legacy))
        return [names[i] for i in resp.json().get("down", []) if i < len(names)]

    async def run_before(self, sticky: bool) -> tuple[str, str, str]:
        await self._post("/target", {"upstreams": self.legacy})
        await self._post("/config", {"sticky": sticky})
        result = await self.runner.run_act("legacy")
        down = await self._down_names()
        return (
            panels.render_results_table(result),
            panels.render_architecture("before", _names(len(self.legacy)), down),
            panels.render_whats_missing(sticky, len(self.legacy)),
        )

    async def run_after(self) -> tuple[str, str, str]:
        await self._post("/target", {"upstreams": self.modern})
        await self._post("/config", {"sticky": False})
        result = await self.runner.run_act("auto")
        return (
            panels.render_results_table(result),
            panels.render_architecture("after", _names(len(self.modern))),
            panels.render_whats_missing(False, len(self.modern)),
        )

    async def kill(self) -> str:
        await self._post("/kill", {"instance": 0})
        down = await self._down_names()
        return panels.render_architecture("before", _names(len(self.legacy)), down)

    async def revive(self) -> str:
        await self._post("/revive", {"instance": 0})
        down = await self._down_names()
        return panels.render_architecture("before", _names(len(self.legacy)), down)

    async def blast(self) -> tuple[str, str]:
        await self._post("/target", {"upstreams": self.modern})
        await self._post("/config", {"sticky": False})
        result = await self.runner.run_blast(50)
        summary = (
            '<div style="border:1px solid #10b981;border-radius:12px;padding:16px;'
            'font:600 15px system-ui;color:#065f46;background:#ecfdf5">'
            f"{result.ok}/{result.total} requests green across instances {result.instances} "
            "&mdash; zero sticky, zero session store</div>"
        )
        served = len(result.instances) or len(self.modern)
        return summary, panels.render_whats_missing(False, served)


def build_demo(settings: Settings | None = None) -> gr.Blocks:
    demo_state = Demo(settings or get_settings())
    initial = _names(len(demo_state.legacy))
    with gr.Blocks(title="MCP goes stateless") as demo:
        gr.Markdown(
            "# MCP is now stateless at the protocol layer\n"
            "Same cart app, same load balancer &mdash; only the protocol changes."
        )
        arch = gr.HTML(panels.render_architecture("before", initial))
        with gr.Row():
            before_btn = gr.Button("① Run BEFORE (stateful, round-robin)", variant="primary")
            sticky = gr.Checkbox(label="sticky routing", value=False)
            kill_btn = gr.Button("💥 Kill inst-0")
            revive_btn = gr.Button("Revive inst-0")
            after_btn = gr.Button("③ Run AFTER (stateless)", variant="primary")
            blast_btn = gr.Button("⚡ Blast ×50")
        with gr.Row():
            table = gr.HTML()
            missing = gr.HTML(panels.render_whats_missing(False, len(demo_state.legacy)))
        gr.Markdown("### What changed in the code")
        gr.HTML(panels.render_change_panel())

        before_btn.click(demo_state.run_before, inputs=[sticky], outputs=[table, arch, missing])
        after_btn.click(demo_state.run_after, outputs=[table, arch, missing])
        kill_btn.click(demo_state.kill, outputs=[arch])
        revive_btn.click(demo_state.revive, outputs=[arch])
        blast_btn.click(demo_state.blast, outputs=[table, missing])
    return demo
