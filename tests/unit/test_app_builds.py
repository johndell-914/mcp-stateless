"""The Gradio app graph builds — cheap guard that every button handler + initial render
resolves. Catches wiring regressions (renamed/removed handlers, bad panel calls) without a
live stack; behavior is covered by the integration tests + live validation.
"""

from __future__ import annotations

from pydantic import SecretStr

from mcp_stateless_demo.config import Settings
from mcp_stateless_demo.ui.gradio_app import Demo, build_demo


def _settings() -> Settings:
    return Settings(token_secret=SecretStr("test-secret"), database_url=SecretStr(""))


def test_build_demo_constructs() -> None:
    demo = build_demo(_settings())
    assert demo is not None


def test_demo_exposes_wired_handlers() -> None:
    # The names build_demo binds to buttons must exist on Demo.
    d = Demo(_settings())
    for handler in (
        "beat1_scale",
        "beat2_sticky",
        "beat3_stateless",
        "beat4_proof",
        "recycle_pod",
        "refresh_logs",
        "intro",
    ):
        assert callable(getattr(d, handler))
    assert d._conv is None  # no live session until a beat starts one
