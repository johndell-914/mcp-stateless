"""Run the proxy: ``python -m mcp_stateless_demo.proxy``."""

from __future__ import annotations

import uvicorn

from ..config import get_settings
from .app import ProxyState, create_proxy_app


def main() -> None:
    settings = get_settings()
    state = ProxyState(settings.upstream_list(), sticky=settings.sticky)
    app = create_proxy_app(state)
    print(f"[proxy] upstreams={state.upstreams} sticky={state.sticky} port={settings.port}")
    uvicorn.run(app, host="0.0.0.0", port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
