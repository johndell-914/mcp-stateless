"""Guard: the Gradio app must actually construct — catches panel call-site/signature drift
that unit-testing the panels in isolation would miss (e.g. a stale arity at a wiring site)."""

from __future__ import annotations


def test_build_demo_constructs() -> None:
    from mcp_stateless_demo.ui.gradio_app import build_demo

    demo = build_demo()
    assert demo is not None
