# Chaufferone FastAPI backend — deployed image.
# Multi-stage: build with uv, run with a slim Python.
FROM python:3.12-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv the same way the project uses locally.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && cp /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /app

# Layer 1: deps only (cached until pyproject/lock change).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Layer 2: source.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY README.md ./README.md
RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -r -u 1000 -m app

WORKDIR /app
COPY --from=build /app /app
RUN mkdir -p /app/data && chown -R app:app /app

USER app
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
