"""Pure HTML renderers for the UI.

No I/O, no framework — each function maps data to an HTML fragment, so they are
snapshot-testable and the Gradio app is a thin wiring layer over them. Styles are inline
so the fragments render identically inside ``gr.HTML`` and in a standalone preview.
"""

from __future__ import annotations

from ..client.runner import ActResult

# palette
_OK = "#10b981"
_ERR = "#ef4444"
_INK = "#1f2937"
_MUTED = "#6b7280"
_BORDER = "#e5e7eb"
_AMBER = "#f59e0b"
_CARD = "border:1px solid #e5e7eb;border-radius:12px;padding:16px;background:#ffffff"


def _instance_badge(name: str | None, *, down: bool = False) -> str:
    if name is None:
        return '<span style="color:#9ca3af">—</span>'
    color = "#9ca3af" if down else "#4f46e5"
    deco = "text-decoration:line-through;opacity:.55" if down else ""
    return (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:999px;'
        f"background:{color}1a;color:{color};"
        f'font:600 12px ui-monospace,monospace;{deco}">{name}</span>'
    )


def render_results_table(result: ActResult) -> str:
    rows = []
    for r in result.rows:
        ok = r.ok
        bg = "#ecfdf5" if ok else "#fef2f2"
        mark = f'<b style="color:{_OK}">OK</b>' if ok else f'<b style="color:{_ERR}">FAIL</b>'
        if ok:
            cart = ", ".join(f'{i["name"]}×{i["qty"]}' for i in (r.cart or [])) or "(empty)"
            detail = cart
        else:
            detail = f'<span style="color:{_ERR}">{r.error or "error"}</span>'
        rows.append(
            f'<tr style="background:{bg}">'
            f'<td style="padding:6px 10px;color:{_MUTED}">{r.n}</td>'
            f'<td style="padding:6px 10px;font:600 13px ui-monospace,monospace">{r.tool}</td>'
            f"<td style=\"padding:6px 10px\">{_instance_badge(r.served_by)}</td>"
            f'<td style="padding:6px 10px">{detail}</td>'
            f'<td style="padding:6px 10px">{mark}</td>'
            f"</tr>"
        )
    head = (
        '<tr style="text-align:left;color:#6b7280;font-size:12px">'
        "<th style='padding:6px 10px'>#</th><th style='padding:6px 10px'>tool</th>"
        "<th style='padding:6px 10px'>served by</th><th style='padding:6px 10px'>cart</th>"
        "<th style='padding:6px 10px'>result</th></tr>"
    )
    return (
        f'<div style="{_CARD}">'
        f'<div style="font:600 14px system-ui;color:{_INK};margin-bottom:8px">'
        f'Requests &nbsp;<span style="color:{_MUTED};font-weight:400">'
        f"mode={result.mode}</span></div>"
        f'<table style="border-collapse:collapse;width:100%;font-size:13px;color:{_INK}">'
        f"{head}{''.join(rows)}</table></div>"
    )


def render_architecture(phase: str, instances: list[str], down: list[str] | None = None) -> str:
    down = down or []
    before = phase == "before"
    boxes = "".join(
        f'<div style="{_CARD};text-align:center;min-width:88px;'
        f'{"opacity:.5" if i in down else ""}">🖥️<br>'
        f'<span style="font:600 12px ui-monospace,monospace">{i}</span>'
        f'{"<br><span style=color:#ef4444;font-size:11px>down</span>" if i in down else ""}</div>'
        for i in instances
    )
    if before:
        lb = (
            f'<div style="{_CARD};text-align:center;border-color:{_AMBER}">'
            f'🔀 <b>Sticky LB</b><br><span style="color:{_MUTED};font-size:11px">'
            f"inspects mcp-session-id<br>on every request</span></div>"
        )
        extra = (
            f'<div style="{_CARD};text-align:center;border-color:{_AMBER};background:#fffbeb">'
            f"🗄️ <b>Redis</b><br>"
            f'<span style="color:{_MUTED};font-size:11px">session store</span></div>'
        )
        tax = (
            f'<div style="margin-top:10px;color:{_AMBER};font:600 13px system-ui">'
            "⚠ the tax: sticky routing + session-aware gateway + a shared store to own</div>"
        )
        title = "BEFORE — session-based protocol"
    else:
        lb = (
            f'<div style="{_CARD};text-align:center;border-color:{_OK}">'
            f'⚖️ <b>Round-robin LB</b><br><span style="color:{_MUTED};font-size:11px">'
            f"any request → any instance</span></div>"
        )
        extra = (
            f'<div style="{_CARD};text-align:center;opacity:.45;text-decoration:line-through">'
            f"🔀 sticky &nbsp; 🗄️ Redis</div>"
        )
        tax = (
            f'<div style="margin-top:10px;color:{_OK};font:600 13px system-ui">'
            "✓ removed: no sticky, no session store, no session-aware gateway</div>"
        )
        title = "AFTER — stateless protocol"

    border = _AMBER if before else _OK
    return (
        f'<div style="{_CARD};border-color:{border}">'
        f'<div style="font:700 14px system-ui;color:{_INK};margin-bottom:12px">{title}</div>'
        f'<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">'
        f'<div style="{_CARD};text-align:center">💻<br><b>Client</b></div>'
        f'<div style="color:{_MUTED};font-size:20px">→</div>{lb}'
        f'<div style="color:{_MUTED};font-size:20px">→</div>'
        f'<div style="display:flex;gap:10px">{boxes}</div>'
        f'<div style="margin-left:8px">{extra}</div></div>{tax}</div>'
    )


def render_whats_missing(sticky: bool, session_store: bool, instances: int) -> str:
    def line(label: str, present: bool) -> str:
        on = f'<span style="color:{_OK}">ON</span>'
        off = f'<span style="color:{_ERR}">OFF</span>'
        icon = on if present else off
        return f'<div style="display:flex;justify-content:space-between;padding:4px 0">' \
               f'<span style="color:{_INK}">{label}</span>{icon}</div>'

    return (
        f'<div style="{_CARD}">'
        f'<div style="font:600 14px system-ui;color:{_INK};margin-bottom:8px">What is running</div>'
        f'<div style="font:13px ui-monospace,monospace">'
        f"{line('sticky routing', sticky)}"
        f"{line('shared session store', session_store)}"
        f'<div style="display:flex;justify-content:space-between;padding:4px 0">'
        f'<span style="color:{_INK}">instances</span>'
        f'<span style="color:#4f46e5">{instances}</span></div>'
        f"</div></div>"
    )


def render_change_panel() -> str:
    def col(title: str, color: str, lines: list[str]) -> str:
        body = "<br>".join(lines)
        return (
            f'<div style="{_CARD};border-color:{color};flex:1">'
            f'<div style="font:700 13px system-ui;color:{color};margin-bottom:8px">{title}</div>'
            f'<div style="font:12px ui-monospace,monospace;color:{_INK};'
            f'line-height:1.7">{body}</div></div>'
        )

    before = col(
        "BEFORE — protocol holds state",
        _AMBER,
        [
            "initialize() → Mcp-Session-Id",
            "&nbsp;&nbsp;session pinned to one instance",
            "tool args: { item }",
        ],
    )
    after = col(
        "AFTER — request holds state",
        _OK,
        [
            "no handshake",
            "&nbsp;&nbsp;_meta carries clientInfo / version",
            "tool args: { cart_token, item }",
        ],
    )
    diff = (
        f'<div style="{_CARD};margin-top:10px;background:#f9fafb">'
        f'<div style="font:12px ui-monospace,monospace;line-height:1.8">'
        f'<span style="color:{_ERR}">- streamable_http_app(stateless_http=False)</span><br>'
        f'<span style="color:{_OK}">+ streamable_http_app(stateless_http=True)</span><br>'
        f'<span style="color:{_ERR}">- Client(url, mode="legacy")</span><br>'
        f'<span style="color:{_OK}">+ Client(url, mode="auto")</span></div>'
        f'<div style="color:{_MUTED};font-size:12px;margin-top:6px">'
        "Two lines — and it is only two lines because the state was already explicit.</div></div>"
    )
    return f'<div style="display:flex;gap:12px">{before}{after}</div>{diff}'
