# One image, three roles. docker-compose sets the `command` (server / proxy / ui).
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    GRADIO_ANALYTICS_ENABLED=False \
    HF_HUB_DISABLE_TELEMETRY=1

# default role; overridden per service in docker-compose.yml
CMD ["python", "-m", "mcp_stateless_demo.server"]
