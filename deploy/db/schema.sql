-- Cart state for the MCP stateless demo.
-- App state lives HERE (survives instance churn); the cart_token handle the client
-- carries is a signed reference to a row's id. Accessed via a direct Postgres
-- connection (asyncpg) — not the REST API — so Row Level Security / anon keys are
-- not involved.

create table if not exists public.carts (
    id          uuid        primary key default gen_random_uuid(),
    items       jsonb       not null default '[]'::jsonb,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);
