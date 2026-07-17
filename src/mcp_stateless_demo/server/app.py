"""Build the server ASGI app.

The *entire* per-act difference lives here: ``stateless_http``. Everything else —
tools, store, token — is identical. That is the on-stage "it's just a flag" moment
made real (principle P1). ``json_response=True`` is held constant in both acts so the
proxy can stay a simple JSON pass-through.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from mcp.server.streamable_http import TransportSecuritySettings
from starlette.applications import Starlette

from ..cart.store import CartStore
from ..cart.token import CartTokenCodec
from ..config import Settings
from .identity import resolve_instance_name
from .tools import register_cart_tools


def build_app(settings: Settings, store: CartStore) -> Starlette:
    server = MCPServer(name="cart-demo")
    codec = CartTokenCodec(settings.token_secret.get_secret_value())
    instance_name = resolve_instance_name(
        settings.instance_id, append_boot_id=settings.append_boot_id
    )
    register_cart_tools(server, store, codec, instance_name)
    return server.streamable_http_app(
        stateless_http=settings.stateless_mode,  # the one line that changes between acts
        json_response=True,
        # Servers sit behind our proxy on an internal network (Docker / Cloud Run), so accept
        # the forwarded Host header instead of only localhost. Constant across both acts.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
