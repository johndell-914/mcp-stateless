# One image, three roles. docker-compose sets the `command` (server / proxy / ui).
FROM python:3.11-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/app/.venv

# Install deps first (cached layer), then the project — so src changes don't re-resolve deps.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --python python3.11
COPY src ./src
RUN uv sync --frozen --no-dev --python python3.11

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    GRADIO_ANALYTICS_ENABLED=False \
    HF_HUB_DISABLE_TELEMETRY=1

# default role; overridden per service in docker-compose.yml
CMD ["python", "-m", "mcp_stateless_demo.server"]
