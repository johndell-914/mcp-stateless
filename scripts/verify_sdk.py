"""verify_sdk.py - Phase-1 gate.

Assert that the mcp SDK API surface this demo is built on actually exists in the
installed package, *before* any code depends on it. Grounded in the verified
evidence recorded in the planning notes (mcp == 2.0.0b2, protocol 2026-07-28).

Run:  uv run python scripts/verify_sdk.py
Exit: 0 if every REQUIRED check passes, 1 otherwise. Optional checks only report.
"""

from __future__ import annotations

import importlib
import inspect
from importlib.metadata import PackageNotFoundError, version

EXPECTED_MCP_VERSION = "2.0.0b2"

_failures: list[str] = []


def _req(label: str, ok: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))
    if not ok:
        _failures.append(label)
    return ok


def _opt(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'ok' if ok else '--'}] (optional) {label}" + (f" - {detail}" if detail else ""))


def main() -> int:
    print("verify_sdk - checking the mcp SDK API surface this demo builds on\n")

    try:
        v: str | None = version("mcp")
    except PackageNotFoundError:
        v = None
    if v == EXPECTED_MCP_VERSION:
        print(f"  [PASS] mcp version == {EXPECTED_MCP_VERSION}")
    else:
        print(f"  [warn] mcp version is {v!r}, expected {EXPECTED_MCP_VERSION} (continuing)")

    print("\nServer (mcp.server.mcpserver.MCPServer):")
    try:
        from mcp.server.mcpserver import MCPServer

        _req("import MCPServer", True)
        params = inspect.signature(MCPServer.streamable_http_app).parameters
        _req("streamable_http_app(stateless_http=...)", "stateless_http" in params)
        _req("streamable_http_app(json_response=...)", "json_response" in params)
        _req("streamable_http_app(streamable_http_path=...)", "streamable_http_path" in params)
        _req("MCPServer.tool decorator", hasattr(MCPServer, "tool"))
        _req("MCPServer.run_streamable_http_async", hasattr(MCPServer, "run_streamable_http_async"))
    except Exception as e:  # noqa: BLE001 - a gate: any failure is a real signal
        _req("import MCPServer", False, repr(e))

    print("\nClient (mcp.Client):")
    try:
        from mcp import Client

        _req("from mcp import Client", True)
        cparams = inspect.signature(Client.__init__).parameters
        _req(
            "Client(mode=...) connect-mode switch",
            "mode" in cparams,
            f"default={cparams['mode'].default!r}" if "mode" in cparams else "",
        )
        _req("Client.call_tool", hasattr(Client, "call_tool"))
    except Exception as e:  # noqa: BLE001
        _req("from mcp import Client", False, repr(e))

    print("\nTransport + headers (mcp.client.streamable_http):")
    try:
        shttp = importlib.import_module("mcp.client.streamable_http")
        transport = shttp.StreamableHTTPTransport
        _req(
            "StreamableHTTPTransport(url=...)",
            "url" in inspect.signature(transport.__init__).parameters,
        )
        _req(
            "MCP_SESSION_ID == 'mcp-session-id'",
            getattr(shttp, "MCP_SESSION_ID", None) == "mcp-session-id",
        )
        _req(
            "MCP_PROTOCOL_VERSION_HEADER == 'mcp-protocol-version'",
            getattr(shttp, "MCP_PROTOCOL_VERSION_HEADER", None) == "mcp-protocol-version",
        )
    except Exception as e:  # noqa: BLE001
        _req("transport + header constants", False, repr(e))

    print("\nProtocol versions (mcp.client._probe):")
    try:
        probe = importlib.import_module("mcp.client._probe")
        modern = getattr(probe, "MODERN_PROTOCOL_VERSIONS", ())
        _req("MODERN_PROTOCOL_VERSIONS contains '2026-07-28'", "2026-07-28" in modern, str(modern))
        _req(
            "LATEST_MODERN_VERSION == '2026-07-28'",
            getattr(probe, "LATEST_MODERN_VERSION", None) == "2026-07-28",
        )
        _req(
            "legacy handshake versions present ('2025-11-25')",
            "2025-11-25" in getattr(probe, "HANDSHAKE_PROTOCOL_VERSIONS", ()),
        )
    except Exception as e:  # noqa: BLE001
        _req("mcp.client._probe protocol versions", False, repr(e))

    print("\nNew-feature surface (optional - referenced by the RC, for future demos):")
    for mod in (
        "mcp.client._input_required",
        "mcp.server.request_state",
        "mcp.server.apps",
        "mcp.server.caching",
        "mcp.client.caching",
    ):
        try:
            importlib.import_module(mod)
            _opt(mod, True)
        except Exception as e:  # noqa: BLE001
            _opt(mod, False, e.__class__.__name__)
    import mcp

    _opt("mcp.InputRequiredRoundsExceededError", hasattr(mcp, "InputRequiredRoundsExceededError"))

    print()
    if _failures:
        print(f"RESULT: FAIL - {len(_failures)} required check(s) failed:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("RESULT: PASS - required API surface present. Safe to build on.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
