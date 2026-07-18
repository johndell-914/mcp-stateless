# MCP goes stateless — a live before/after demo

A working demonstration of the change introduced in the **Model Context Protocol
`2026-07-28` release candidate**: MCP becomes **stateless at the protocol layer**. The
`initialize` handshake and the `Mcp-Session-Id` header are gone, so a server that used to
need **sticky routing + a shared session store** to scale can now run behind a plain
round-robin load balancer — *any request can land on any instance*.

This repo shows that shift two ways: an **interactive diagram** you can open in a browser,
and a **live demo** that drives real MCP servers on Google Cloud Run and proves the behavior
with the platform's own logs.

![The "before" architecture — the session tax](assets/diagram-before.png)

> `<Agent> → <Sticky gateway> → <Session store> → <instances> → <Postgres>` — everything
> in amber is the operational tax the old protocol forced on you. The new protocol deletes it.

---

## The thesis

You build an MCP server. It works on your laptop. Then you deploy it for 50,000 users.

Every agent conversation is a **session**. Under the old protocol the server minted a session
id on `initialize`, and that session lived in **one instance's memory**. Put two instances
behind a load balancer and the agent's next tool call lands on the other one — *"Session not
found."* To cope you bolt on **sticky routing** and a **shared session store**, and when a pod
recycles, live agents drop mid-task.

The `2026-07-28` protocol makes MCP stateless: state moves into an **explicit token** the
client carries as a tool argument (`cart_token`), so any instance can serve any request. The
migration is two lines — because the app state was already explicit; the protocol was just
forcing a session on top of it.

This demo uses a tiny **shopping-cart** MCP server (`create_cart` / `add_item` / `get_cart`) —
exactly the shape of a real agentic-commerce server (Shopify, Stripe, and others ship remote
MCP servers today). The tools never change between "before" and "after"; only the protocol flag
and the client mode do.

---

## What's in the box

| Surface | What it is | How to view |
| --- | --- | --- |
| **Interactive diagram** | Self-contained HTML — Narrative / Before / After / The Change / At Scale tabs, a Technical⇄Plain toggle, light/dark + fullscreen | Open [`MCP-STATELESS-DEMO.html`](MCP-STATELESS-DEMO.html) in any browser (no build, no network) |
| **Live demo** | A Gradio app that drives real MCP servers on Cloud Run and shows live results + real Cloud Run logs | Run locally (below) or deploy your own |

### The four beats

The live demo walks a guided story with the **same three tools** each time:

1. **① Scale it** — round-robin over two instances → *"Session not found."* The break, proven by real `404`s across two instance IDs in the logs.
2. **② Add the tax** — turn on sticky routing (+ a session store in the diagram) → it works, but you now own a session-aware gateway and an external store.
3. **💥 Recycle a pod** — with sticky on, recycle the instance holding a live session → the agent **drops mid-task**.
4. **③ Go stateless** — flip the protocol → every request succeeds across instances, nothing extra to own.
5. **④ Prove it at scale** — blast 60 concurrent agents at a real autoscaling service → Cloud Run fans out to N instances, every request green, proven by the platform's own instance IDs in the logs.

![Under load — real Cloud Run autoscale](assets/diagram-at-scale.png)

---

## The change — it's two lines

```diff
# server
- streamable_http_app(stateless_http=False)
+ streamable_http_app(stateless_http=True)

# client
- Client(url, mode="legacy")
+ Client(url, mode="auto")
```

The tool bodies are byte-identical across both modes. The cart always lives in Postgres,
addressed by a signed, opaque `cart_token` the client passes back — that's why the migration
is so small.

---

## How it works

The demo runs as several small services so a load balancer can genuinely round-robin across
*distinct process memories*:

```mermaid
flowchart LR
    A["🧑‍💻 Agent<br/>(the Gradio UI drives it)"] --> P["Proxy load balancer<br/>round-robin · sticky · kill/revive"]
    P --> L["legacy-a / legacy-b<br/>stateless_http = False"]
    P --> M["modern-a / modern-b<br/>stateless_http = True"]
    A -. "beat ④ blast" .-> S["scale service<br/>autoscaling, concurrency=1"]
    L --> DB[("Supabase<br/>Postgres")]
    M --> DB
    S --> DB
```

- **`server/`** — a `MCPServer` exposing the three cart tools. The *entire* per-act difference
  is one flag (`stateless_http`); everything else is constant.
- **`proxy/`** — a deterministic reverse proxy: plain round-robin, or *learned* sticky affinity
  (session-id → instance), plus `/kill` + `/revive` for the recycle beat. This is the "load
  balancer / session-aware gateway" the audience watches.
- **`cart/`** — the domain: the `cart_token` codec (HMAC-signed handle), the store `Protocol`,
  and the Postgres store.
- **`client/`** — the `ActRunner` that drives scripted acts (and the 60-way blast) through the
  proxy and returns structured rows.
- **`cloud/`** — reads real Cloud Run stdout logs so the UI can *prove* an event happened on
  real infrastructure.
- **`ui/`** — the Gradio app (thin wiring) and the pure HTML panel renderers.

App state lives in Postgres (it survives instance churn); the client carries only a signed
reference to a row. Row Level Security / anon keys aren't involved — the server connects
directly with `asyncpg`.

---

## Anatomy of a tool call

Trace one request end-to-end and the codebase falls into place. Here's `add_item`:

```mermaid
sequenceDiagram
    participant A as Agent · client/runner.py
    participant P as Proxy · proxy/app.py
    participant S as MCP server · server/tools.py
    participant T as Token · cart/token.py
    participant DB as Postgres · cart/store_postgres.py
    A->>P: POST /mcp — tools/call add_item {cart_token, name, qty}
    P->>S: forward (round-robin / sticky; reads mcp-session-id)
    S->>T: codec.decode(cart_token) → verify HMAC → cart_id
    S->>DB: update carts set items = items || $2 where id = cart_id
    DB-->>S: updated items
    S-->>A: {served_by, cart_token, items}
```

1. **Agent** — [`client/runner.py`](src/mcp_stateless_demo/client/runner.py) opens `Client(url, mode=…)` and calls `client.call_tool("add_item", {…})`; the MCP SDK serializes a JSON-RPC `tools/call` and POSTs it over streamable HTTP. In stateless mode there's no `initialize`/session-id handshake.
2. **Proxy** — [`proxy/app.py`](src/mcp_stateless_demo/proxy/app.py) reads one header (`mcp-session-id`), `state.pick()`s an instance (round-robin or learned sticky), and forwards the raw bytes.
3. **Server** — [`server/tools.py`](src/mcp_stateless_demo/server/tools.py) runs the `@server.tool()` function. With `stateless_http=False` the transport first checks the session belongs to *this* instance (a `404 "Session not found"` otherwise — that's the "before" break, before your tool even runs).
4. **Token** — [`cart/token.py`](src/mcp_stateless_demo/cart/token.py) re-signs the id and `compare_digest`s it, then returns the `cart_id` (a client can't forge one it wasn't given).
5. **Store** — [`cart/store_postgres.py`](src/mcp_stateless_demo/cart/store_postgres.py) appends the item with a jsonb `||` and returns the updated cart.

`create_cart` is the same path minus the decode: it `insert`s a row (`store.create()`) and returns `codec.encode(cart_id)` — the signed handle the client carries into every later call.

**Why this shape matters:** `add_item` needs *nothing* from server memory — the `cart_token` + Postgres hold all the state, so any instance can serve any call. That's the explicit-handle pattern, and it's why flipping `stateless_http` is a two-line change rather than a rewrite. (The interactive diagram's **Request Flow** tab walks this same sequence visually.)

---

## Run it locally

You need Docker and a Postgres database (Supabase's free tier works well).

```bash
# 1. configure
cp .env.example .env
#    fill DATABASE_URL (Supabase session-pooler URI, port 5432) and TOKEN_SECRET:
#    python -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. create the table
psql "$DATABASE_URL" -f deploy/db/schema.sql      # or paste it into the Supabase SQL editor

# 3. run the whole stack (2 legacy + 2 modern servers, the proxy, the UI)
docker compose up --build
```

Then open **http://localhost:7860** and walk the four beats.

## Development

```bash
uv sync --extra dev
uv run pytest                                             # tests
uv run ruff check src tests                               # lint
uv run mypy --strict src/mcp_stateless_demo/cart src/mcp_stateless_demo/client   # strict types on the load-bearing modules
```

## Deploy to Cloud Run

The `Dockerfile` builds one image; each service picks its role via env vars / command. In
outline:

1. Build + push the image (Cloud Build → Artifact Registry).
2. Put `DATABASE_URL` and `TOKEN_SECRET` in Secret Manager; grant the runtime service account
   `secretmanager.secretAccessor`.
3. Deploy the four servers (`STATELESS_MODE=0|1`), the proxy (`-m ...proxy`), and the UI
   (`-m ...ui`), wiring the URLs through env vars.

Once deployed, ship changes with the included script (an image-only redeploy that preserves
any auth/network settings):

```bash
bash deploy/redeploy.sh                    # rebuild + redeploy the UI
bash deploy/redeploy.sh mcp-stateless-proxy  # or a specific service
```

---

## Tech stack

`mcp[cli]==2.0.0b2` · Starlette · Uvicorn · Gradio · `asyncpg` + Supabase Postgres ·
`pydantic-settings` · Google Cloud Run · Python 3.11 · [uv](https://github.com/astral-sh/uv).

---

<sub>Built for the **AAIF Community Series — Agentic AI Night** (Agentic AI Foundation, Seattle).</sub>
