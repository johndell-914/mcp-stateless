"""Pure HTML renderers for the demo UI.

No I/O, no framework — each function maps data to an HTML fragment, so they are
snapshot-testable and the Gradio app is a thin wiring layer over them. Styles are inline
(and colors explicit) so fragments render identically inside ``gr.HTML`` regardless of the
Gradio theme, and read on a projector from the back of a room.
"""

from __future__ import annotations

import re

from ..client.runner import ActResult
from ..cloud.logs import LogLine, LogProof

# ── palette ───────────────────────────────────────────────────────────────────────────
_INK = "#0f172a"
_MUTED = "#64748b"
_FAINT = "#94a3b8"
_LINE = "#e5e7eb"
_INDIGO = "#4f46e5"
_OK = "#10b981"
_ERR = "#ef4444"
_AMBER = "#f59e0b"
_BG = "#ffffff"
_WASH = "#f8fafc"

_MONO = "ui-monospace,SFMono-Regular,Menlo,monospace"
_SANS = "system-ui,-apple-system,Segoe UI,Roboto,sans-serif"
_CARD = (
    f"border:1px solid {_LINE};border-radius:14px;padding:16px;background:{_BG};"
    f"color:{_INK};box-shadow:0 1px 2px rgba(15,23,42,.04),0 4px 12px rgba(15,23,42,.04)"
)

# One <style> block, injected with fragments (idempotent — same keyframe names).
_ANIM = (
    "<style>"
    "@keyframes mcpPulse{0%{box-shadow:0 0 0 0 rgba(79,70,229,.45)}"
    "70%{box-shadow:0 0 0 10px rgba(79,70,229,0)}100%{box-shadow:0 0 0 0 rgba(79,70,229,0)}}"
    "@keyframes mcpFade{from{opacity:0;transform:translateY(3px)}to{opacity:1;transform:none}}"
    ".mcp-served{animation:mcpPulse 1.4s ease-out 2}"
    ".mcp-row{animation:mcpFade .25s ease-out both}"
    "</style>"
)


def _chip(text: str, *, color: str, bg: str | None = None, strike: bool = False) -> str:
    bg = bg or f"{color}14"
    deco = "text-decoration:line-through;opacity:.5;" if strike else ""
    return (
        f'<span style="display:inline-block;padding:2px 9px;border-radius:999px;background:{bg};'
        f'color:{color};font:600 12px {_MONO};{deco}">{text}</span>'
    )


# ── beat 0 — the scenario ───────────────────────────────────────────────────────────────
def render_scenario() -> str:
    call = lambda t: (  # noqa: E731
        f'<span style="font:600 12px {_MONO};color:{_INDIGO};background:{_INDIGO}12;'
        f'padding:2px 8px;border-radius:6px;white-space:nowrap">{t}</span>'
    )
    return (
        f'<div style="{_CARD};border-left:4px solid {_INDIGO}">'
        f'<div style="font:600 12px {_SANS};letter-spacing:.08em;text-transform:uppercase;'
        f'color:{_MUTED};margin-bottom:6px">The scenario</div>'
        f'<div style="font:700 22px/1.3 {_SANS};color:{_INK};margin-bottom:10px">'
        "You built an MCP server. It works on your laptop.<br>"
        f'Now ship it to <span style="color:{_INDIGO}">50,000 users</span>.</div>'
        f'<div style="font:14px/1.6 {_SANS};color:{_MUTED};margin-bottom:12px">'
        "Every agent conversation is a <b style=\"color:#0f172a\">session</b>. A shopping "
        "assistant builds a cart across turns — the model calls tools as the user talks:</div>"
        f'<div style="background:{_WASH};border:1px solid {_LINE};border-radius:10px;padding:12px">'
        f'<div style="font:13px {_SANS};color:{_INK};margin-bottom:8px">'
        '🧑 <i>"add two apples and a banana to my cart, then show me the total"</i></div>'
        f'<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">'
        f'<span style="color:{_FAINT};font:12px {_SANS}">🤖 agent calls</span>'
        f"{call('create_cart()')}{call('add_item(apple×2)')}"
        f"{call('add_item(banana)')}{call('get_cart()')}</div></div>"
        f'<div style="margin-top:11px;font:12.5px/1.5 {_SANS};color:{_MUTED}">'
        f'<b style="color:{_INK}">A real, live MCP pattern</b> — agentic commerce (Shopify, '
        "Stripe & others ship remote MCP servers). These three tools are exactly what a commerce "
        "MCP server exposes; the app was never the problem, the protocol was.</div></div>"
    )


# ── stepper ─────────────────────────────────────────────────────────────────────────────
_STEPS = [("1", "Scale it"), ("2", "The tax"), ("3", "Go stateless"), ("4", "Prove at scale")]


def render_stepper(active: int) -> str:
    cells = []
    for i, (num, label) in enumerate(_STEPS, start=1):
        done = i < active
        now = i == active
        if now:
            bg, fg, bd = _INDIGO, "#ffffff", _INDIGO
        elif done:
            bg, fg, bd = f"{_OK}14", _OK, _OK
        else:
            bg, fg, bd = _BG, _FAINT, _LINE
        mark = "✓" if done else num
        cells.append(
            f'<div style="display:flex;align-items:center;gap:8px">'
            f'<span style="display:inline-flex;align-items:center;justify-content:center;'
            f"width:26px;height:26px;border-radius:999px;border:1.5px solid {bd};"
            f'background:{bg};color:{fg};font:700 13px {_SANS}">{mark}</span>'
            f'<span style="font:600 13px {_SANS};color:{_INK if now else _MUTED}">{label}</span>'
            "</div>"
        )
        if i < len(_STEPS):
            cells.append(f'<div style="flex:1;height:2px;background:{_LINE};min-width:18px"></div>')
    return (
        f'<div style="{_CARD};padding:14px 18px">'
        f'<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">'
        f'{"".join(cells)}</div></div>'
    )


# ── narrative (key phrase per beat) ─────────────────────────────────────────────────────
_NARRATIVE: dict[str, tuple[str, str, str]] = {
    "intro": (
        _INDIGO,
        "Same cart app, same load balancer — only the protocol changes.",
        "Walk the four steps. Watch where identity lives, and what you have to bolt on to scale.",
    ),
    "scale": (
        _ERR,
        "The agent forgot who it was talking to.",
        "Plain round-robin, two instances. The session is minted on one instance; the next "
        "call lands on the other — “Session not found.” Every follow-up request is a coin flip.",
    ),
    "sticky": (
        _AMBER,
        "It works — but look what you had to add.",
        "Pin every session to its instance (sticky routing) and add a shared session store. "
        "You now own a session-aware gateway and an external store. That is the operational tax.",
    ),
    "recycle": (
        _AMBER,
        "And it is fragile: recycle a pod and that agent drops mid-task.",
        "Sticky is on, yet when the instance holding a live session is recycled, that "
        "conversation is gone — even though the load balancer is doing its job.",
    ),
    "recycle_survive": (
        _OK,
        "Recycle a pod — the agent doesn't even notice.",
        "Stateless, plain round-robin. Recycle the very instance that created the cart and the "
        "next call just lands on another — the cart_token + Postgres carry the state. The same "
        "recycle that dropped the sticky session is a non-event here.",
    ),
    "recycle_none": (
        _MUTED,
        "No live session to recycle yet.",
        "Run ② Add the tax or ③ Go stateless first — that starts a live agent session on a "
        "real pod. Then recycle that pod and watch what the protocol does.",
    ),
    "stateless": (
        _OK,
        "Delete the gateway. Delete the store.",
        "The 2026-07-28 spec makes MCP stateless: no handshake, no session id — state rides in "
        "an explicit token. Any request runs on any instance behind a plain round-robin LB.",
    ),
    "proof": (
        _OK,
        "Any request, any instance — autoscale freely.",
        "60 concurrent agents, real Cloud Run autoscaling, zero sticky, zero store. Cloud Run "
        "fans out to many instances and every request is green — proven by the platform’s logs.",
    ),
}


def render_narrative(beat: str) -> str:
    color, headline, body = _NARRATIVE.get(beat, _NARRATIVE["intro"])
    return (
        f'<div style="{_CARD};border-left:4px solid {color}">'
        f'<div style="font:700 19px/1.35 {_SANS};color:{_INK};margin-bottom:6px">{headline}</div>'
        f'<div style="font:14px/1.6 {_SANS};color:{_MUTED}">{body}</div></div>'
    )


# ── live architecture strip ─────────────────────────────────────────────────────────────
def _instance_card(name: str, *, down: bool, served: bool) -> str:
    if down:
        border, ink = _LINE, _FAINT
    elif served:
        border, ink = _INDIGO, _INDIGO
    else:
        border, ink = _LINE, _INK
    cls = "mcp-served" if served and not down else ""
    badge = (
        f'<div style="color:{_ERR};font:600 10px {_SANS};margin-top:3px">recycled</div>'
        if down
        else (
            f'<div style="color:{_OK};font:600 10px {_SANS};margin-top:3px">● served</div>'
            if served
            else ""
        )
    )
    opacity = "opacity:.45;" if down else ""
    return (
        f'<div class="{cls}" style="border:2px solid {border};border-radius:12px;'
        f"padding:12px 16px;background:{_BG};text-align:center;min-width:104px;{opacity}"
        f'{"text-decoration:line-through;" if down else ""}">'
        f'<div style="font-size:26px">🖥️</div>'
        f'<div style="font:700 13px {_MONO};color:{ink};white-space:nowrap">{name}</div>'
        f"{badge}</div>"
    )


def _arrow() -> str:
    return f'<div style="color:{_FAINT};font-size:20px;padding:0 2px">→</div>'


def render_architecture(
    view: str,
    instances: list[str],
    *,
    sticky: bool = False,
    store: bool = False,
    down: list[str] | None = None,
    served: list[str] | None = None,
    scaling: bool = False,
) -> str:
    down = down or []
    served = served or []
    is_after = view in ("after", "scale")

    if view == "scale":
        lb_title, lb_sub, lb_color = "Cloud Run LB", "autoscales on demand", _OK
    elif sticky:
        lb_title, lb_sub, lb_color = "Sticky gateway", "inspects mcp-session-id", _AMBER
    else:
        lb_title, lb_sub, lb_color = "Round-robin LB", "any request → any instance", (
            _OK if is_after else _MUTED
        )

    lb = (
        f'<div style="border:1.5px solid {lb_color};border-radius:10px;padding:10px 12px;'
        f'background:{_BG};text-align:center;min-width:120px">'
        f'<div style="font:700 13px {_SANS};color:{_INK}">{lb_title}</div>'
        f'<div style="font:11px {_SANS};color:{_MUTED};margin-top:2px">{lb_sub}</div></div>'
    )

    store_card = ""
    if store:
        store_card = (
            f'<div style="border:1.5px dashed {_AMBER};border-radius:10px;padding:10px 12px;'
            f'background:{_AMBER}0d;text-align:center;min-width:96px">'
            f'<div style="font-size:16px">🗄️</div>'
            f'<div style="font:700 12px {_SANS};color:{_INK}">session store</div>'
            f'<div style="font:10px {_SANS};color:{_MUTED}">Redis — to own</div></div>'
        )

    cards = "".join(
        _instance_card(n, down=n in down, served=n in served) for n in instances
    )
    grid = (
        f'<div style="display:flex;gap:8px;flex-wrap:wrap;max-width:420px">{cards}</div>'
    )

    # header + caption per view
    if view == "scale":
        title = "UNDER LOAD — real Cloud Run autoscale"
        cap_c = _OK
        cap = f"⚡ {len(instances)} instances serving · every request green · no sticky, no store"
        border = _OK
    elif is_after:
        title = "AFTER — stateless protocol"
        cap_c, cap = _OK, "✓ removed: no sticky routing, no session store, no session-aware gateway"
        border = _OK
    else:
        title = "BEFORE — session-based protocol"
        if sticky:
            cap_c = _AMBER
            cap = "⚠ the tax: sticky routing + a session-aware gateway + a shared store to run"
        else:
            cap_c = _MUTED
            cap = "plain round-robin — the naive deploy every follow-up call is a coin flip"
        border = _AMBER

    scale_badge = (
        f'<span style="margin-left:8px;padding:2px 8px;border-radius:999px;background:{_OK}14;'
        f'color:{_OK};font:600 11px {_SANS}">▲ autoscaling</span>'
        if scaling
        else ""
    )
    agent = (
        f'<div style="border:1.5px solid {_LINE};border-radius:10px;padding:10px 12px;'
        f'background:{_BG};text-align:center;min-width:80px">'
        f'<div style="font-size:18px">🧑‍💻</div>'
        f'<div style="font:600 12px {_SANS};color:{_INK}">agents</div></div>'
    )
    # The cart always lives in Postgres, addressed by the token — the point of the whole demo.
    db = (
        f'<div style="border:1.5px solid {_LINE};border-radius:12px;padding:12px 16px;'
        f'background:{_BG};text-align:center;min-width:104px">'
        f'<div style="font-size:26px">🐘</div>'
        f'<div style="font:700 13px {_SANS};color:{_INK}">Supabase</div>'
        f'<div style="font:10px {_SANS};color:{_MUTED}">cart lives here</div></div>'
    )
    return (
        f"{_ANIM}"
        f'<div style="{_CARD};border-color:{border}">'
        f'<div style="font:700 13px {_SANS};letter-spacing:.04em;color:{_INK};margin-bottom:12px">'
        f"{title}{scale_badge}</div>"
        f'<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">'
        f"{agent}{_arrow()}{lb}"
        f"{(_arrow() + store_card) if store else ''}"
        f"{_arrow()}{grid}{_arrow()}{db}</div>"
        f'<div style="margin-top:12px;color:{cap_c};font:600 13px {_SANS}">{cap}</div>'
        "</div>"
    )


# ── request results table ───────────────────────────────────────────────────────────────
def render_results_table(result: ActResult) -> str:
    rows = []
    for r in result.rows:
        ok = r.ok
        bg = f"{_OK}0d" if ok else f"{_ERR}0d"
        mark = (
            f'<b style="color:{_OK}">OK</b>' if ok else f'<b style="color:{_ERR}">FAIL</b>'
        )
        if ok:
            cart = ", ".join(f'{i["name"]}×{i["qty"]}' for i in (r.cart or [])) or "(empty)"
            detail = f'<span style="color:{_INK}">{cart}</span>'
        else:
            detail = f'<span style="color:{_ERR}">{r.error or "error"}</span>'
        served = (
            _chip(r.served_by, color=_INDIGO)
            if r.served_by
            else f'<span style="color:{_FAINT}">—</span>'
        )
        rows.append(
            f'<tr class="mcp-row" style="background:{bg}">'
            f'<td style="padding:7px 10px;color:{_MUTED};font:12px {_MONO}">{r.n}</td>'
            f'<td style="padding:7px 10px;font:600 13px {_MONO};color:{_INK}">{r.tool}</td>'
            f'<td style="padding:7px 10px">{served}</td>'
            f'<td style="padding:7px 10px;font:13px {_SANS}">{detail}</td>'
            f'<td style="padding:7px 10px">{mark}</td></tr>'
        )
    head = (
        f'<tr style="text-align:left;color:{_MUTED};font:12px {_SANS}">'
        '<th style="padding:6px 10px">#</th><th style="padding:6px 10px">tool</th>'
        '<th style="padding:6px 10px">served by</th><th style="padding:6px 10px">cart</th>'
        '<th style="padding:6px 10px">result</th></tr>'
    )
    return (
        f"{_ANIM}<div style=\"{_CARD}\">"
        f'<div style="font:600 14px {_SANS};color:{_INK};margin-bottom:8px">Requests '
        f'<span style="color:{_MUTED};font-weight:400">· mode {result.mode}</span></div>'
        f'<table style="border-collapse:collapse;width:100%">{head}{"".join(rows)}</table></div>'
    )


def render_blast_summary(
    ok: int, total: int, instances: list[str], counts: list[tuple[str, int]] | None = None
) -> str:
    all_green = ok == total
    color = _OK if all_green else _ERR
    counts = counts or [(i, 0) for i in instances]
    maxc = max((c for _, c in counts), default=1) or 1
    bars = "".join(
        '<div style="display:flex;align-items:center;gap:10px;margin:4px 0">'
        f'<span style="flex:0 0 96px;font:600 12px {_MONO};color:{_INDIGO}">{inst}</span>'
        f'<div style="flex:1;background:{_WASH};border:1px solid {_LINE};border-radius:6px;'
        'height:18px;overflow:hidden">'
        f'<div style="width:{max(6, round(c / maxc * 100))}%;height:100%;background:{_INDIGO}">'
        "</div></div>"
        f'<span style="flex:0 0 60px;font:700 12px {_MONO};color:{_INK}">{c} req</span></div>'
        for inst, c in counts
    )
    return (
        f'<div style="{_CARD};border-color:{color}">'
        f'<div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap">'
        f'<div style="font:800 30px {_SANS};color:{color}">{ok}/{total}</div>'
        f'<div style="font:600 15px {_SANS};color:{_INK}">requests green</div>'
        f'<div style="font:14px {_SANS};color:{_MUTED}">fanned out across '
        f'<b style="color:{_INK}">{len(instances)}</b> autoscaled instances</div></div>'
        f'<div style="margin-top:12px;font:600 12px {_SANS};color:{_MUTED};margin-bottom:4px">'
        f"requests handled per instance</div>{bars}"
        f'<div style="margin-top:12px;color:{color};font:600 13px {_SANS}">'
        "zero sticky · zero session store · any request on any instance</div></div>"
    )


# ── real-log proof panel (terminal styled) ──────────────────────────────────────────────
_STATUS_RE = re.compile(r'HTTP/1\.1"\s+(\d{3})')


def _status_of(text: str) -> str:
    m = _STATUS_RE.search(text)
    return m.group(1) if m else ""


def _status_color(code: str) -> str:
    if code.startswith("2"):
        return "#6ee7b7"  # green — served
    if code.startswith(("4", "5")):
        return "#f87171"  # red — session not found / error
    return "#cbd5e1"


def render_log_proof(proof: LogProof | None, *, headline: str, subtitle: str = "") -> str:
    term_bg = "#0b1020"
    if proof is None:
        body = (
            f'<div style="color:{_FAINT};font:13px {_MONO}">run a step to pull live logs…</div>'
        )
        count_chip = ""
    elif not proof.ok:
        body = (
            f'<div style="color:{_AMBER};font:12px {_MONO}">logs unavailable '
            f'({proof.error or "no credentials"}) — see the Cloud Run console tab</div>'
        )
        count_chip = ""
    elif not proof.lines:
        body = (
            f'<div style="color:{_FAINT};font:13px {_MONO}">no matching log lines yet '
            "(a few seconds of ingestion lag)…</div>"
        )
        count_chip = ""
    else:
        # status tally across ALL lines (green 200s, red 404s = "session not found")
        tally: dict[str, int] = {}
        for ln in proof.lines:
            code = _status_of(ln.text)
            if code:
                tally[code] = tally.get(code, 0) + 1
        summary = " · ".join(
            f'<span style="color:{_status_color(c)};font-weight:700">{n}×{c}</span>'
            for c, n in sorted(tally.items())
        )
        summary_line = (
            f'<div style="color:#64748b;border-bottom:1px solid #1e2740;padding-bottom:6px;'
            f'margin-bottom:6px">{len(proof.lines)} requests · {summary}</div>'
            if summary
            else ""
        )
        shown = proof.lines[:12]

        def _paint(m: re.Match[str]) -> str:
            code = m.group(2)
            return (
                f'{m.group(1)} <span style="color:{_status_color(code)};font-weight:700">'
                f"{code}{m.group(3)}</span>"
            )

        def _line(ln: LogLine) -> str:
            text = re.sub(r'(HTTP/1\.1")\s+(\d{3})(.*)$', _paint, ln.text)
            return (
                '<div style="display:flex;gap:10px;padding:1px 0">'
                f'<span style="color:#64748b;flex:0 0 62px">{ln.ts}</span>'
                f'<span style="color:#93c5fd;flex:0 0 108px">{ln.instance or "—"}</span>'
                '<span style="color:#a7f3d0;white-space:nowrap;overflow:hidden;'
                f'text-overflow:ellipsis">{text}</span></div>'
            )

        line_html = "".join(_line(ln) for ln in shown)
        body = f'<div style="font:12px/1.6 {_MONO}">{summary_line}{line_html}</div>'
        count_chip = (
            f'<span style="padding:3px 10px;border-radius:999px;background:{_OK}1f;color:{_OK};'
            f'font:700 13px {_SANS}">{proof.instance_count} distinct instances</span>'
        )
    sub = (
        f'<div style="font:12px {_SANS};color:{_MUTED};margin-top:2px">{subtitle}</div>'
        if subtitle
        else ""
    )
    return (
        f'<div style="{_CARD}">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;gap:10px">'
        f'<div><div style="font:600 14px {_SANS};color:{_INK}">{headline}</div>{sub}</div>'
        f"{count_chip}</div>"
        f'<div style="margin-top:10px;background:{term_bg};border-radius:10px;padding:12px 14px;'
        f'overflow-x:auto">{body}</div>'
        f'<div style="font:11px {_SANS};color:{_FAINT};margin-top:6px">'
        "▲ real Cloud Run stdout · instance id = the platform’s own, not ours</div></div>"
    )


# ── the code change (migration payload) ─────────────────────────────────────────────────
def render_change_panel() -> str:
    def col(title: str, color: str, lines: list[str]) -> str:
        body = "<br>".join(lines)
        return (
            f'<div style="{_CARD};border-color:{color};flex:1;min-width:220px">'
            f'<div style="font:700 13px {_SANS};color:{color};margin-bottom:8px">{title}</div>'
            f'<div style="font:12px/1.7 {_MONO};color:{_INK}">{body}</div></div>'
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
        f'<div style="{_CARD};margin-top:10px;background:{_WASH}">'
        f'<div style="font:12px/1.8 {_MONO}">'
        f'<span style="color:{_ERR}">- streamable_http_app(stateless_http=False)</span><br>'
        f'<span style="color:{_OK}">+ streamable_http_app(stateless_http=True)</span><br>'
        f'<span style="color:{_ERR}">- Client(url, mode="legacy")</span><br>'
        f'<span style="color:{_OK}">+ Client(url, mode="auto")</span></div>'
        f'<div style="color:{_MUTED};font:12px {_SANS};margin-top:6px">'
        "Two lines — and it is only two lines because the state was already explicit.</div></div>"
    )
    return f'<div style="display:flex;gap:12px;flex-wrap:wrap">{before}{after}</div>{diff}'


def _aaif_mark() -> str:
    # The real AAIF mark: 4 big circles (2x2) interlocking with a 3x3 grid of small squares.
    circles = "".join(f'<circle cx="{cx}" cy="{cy}" r="13"/>' for cy in (35, 65) for cx in (35, 65))
    squares = "".join(
        f'<rect x="{x}" y="{y}" width="10" height="10" rx="1.5"/>'
        for y in (11, 45, 79)
        for x in (11, 45, 79)
    )
    return (
        '<span style="display:inline-flex;background:#0e1420;border-radius:8px;padding:5px;'
        'line-height:0;box-shadow:0 0 0 1px rgba(255,255,255,.12)">'
        f'<svg width="24" height="24" viewBox="0 0 100 100" fill="#fff">{circles}{squares}</svg>'
        "</span>"
    )


def _ms_mark(color: str) -> str:
    one = f'<span style="width:7px;height:7px;background:{color}"></span>'
    cells = one * 4
    return (
        '<span style="display:inline-grid;grid-template-columns:repeat(2,7px);'
        f'grid-auto-rows:7px;gap:2px">{cells}</span>'
    )


def render_brand_footer() -> str:
    """AAIF hosted-by footer — matches the standalone diagram (large pills, no series line)."""
    pill = (
        "display:inline-flex;align-items:center;gap:10px;height:44px;padding:0 18px;"
        f"border:1px solid {_LINE};border-radius:10px;background:{_BG};"
        f"font:700 14px {_SANS};color:{_INK};white-space:nowrap"
    )
    return (
        f'<div style="{_CARD};margin-top:4px;display:flex;flex-direction:column;'
        'align-items:center;gap:12px">'
        '<div style="display:flex;align-items:center;justify-content:center;'
        'gap:14px;flex-wrap:wrap">'
        f'<span style="font:700 12px {_SANS};letter-spacing:.1em;color:{_MUTED}">HOSTED BY</span>'
        f'<span style="{pill}">{_aaif_mark()} Agentic AI Foundation</span>'
        f'<span style="font:700 11px {_MONO};letter-spacing:.14em;color:{_FAINT}">WITH</span>'
        f'<span style="{pill}">{_ms_mark(_INK)} Microsoft</span>'
        f'<span style="{pill}">Opaque</span></div>'
        f'<span style="font:700 11px {_MONO};letter-spacing:.14em;color:{_FAINT};'
        'text-align:center">AAIF.IO / COMMUNITY</span></div>'
    )
