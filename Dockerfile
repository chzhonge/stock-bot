FROM python:3.11-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ ./src/
RUN uv sync --locked --no-editable

FROM python:3.11-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 bot \
    && useradd --uid 10001 --gid bot --create-home bot \
    && install -d -o bot -g bot /app/data

COPY --from=builder /app/.venv /app/.venv
COPY scripts/ ./scripts/

USER bot
CMD ["stock-chart-bot", "--config", "/app/config.toml"]
