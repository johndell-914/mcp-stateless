"""Launch the Gradio UI: ``python -m mcp_stateless_demo.ui``."""

from __future__ import annotations

import gradio as gr

from ..config import get_settings
from .gradio_app import build_demo


def main() -> None:
    settings = get_settings()
    demo = build_demo(settings)
    auth = None
    if ":" in settings.ui_auth:
        user, password = settings.ui_auth.split(":", 1)
        auth = (user, password)
    theme = gr.themes.Soft(primary_hue="indigo", secondary_hue="slate")
    demo.launch(server_name="0.0.0.0", server_port=settings.port, auth=auth, theme=theme)


if __name__ == "__main__":
    main()
