# syntax=docker/dockerfile:1

FROM python:3.11-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ ./src/
RUN uv sync --locked --no-editable

FROM scratch AS supercronic-amd64
ADD --checksum=sha256:cc232108374e8e2b537045f2d5eaa1229f619db314c3ba6a14d38b35dc0aa123 --chmod=0755 \
    https://github.com/aptible/supercronic/releases/download/v0.2.51/supercronic-linux-amd64 \
    /supercronic

FROM scratch AS supercronic-arm64
ADD --checksum=sha256:4ae22576a78223d8ccdf5f3b3660a5cbb5288416bf0ca96afc4a36d195932b94 --chmod=0755 \
    https://github.com/aptible/supercronic/releases/download/v0.2.51/supercronic-linux-arm64 \
    /supercronic

FROM supercronic-${TARGETARCH} AS supercronic

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
COPY --from=supercronic /supercronic /usr/local/bin/supercronic
COPY scripts/ ./scripts/
COPY deploy/cron/crontab ./crontab

USER bot
CMD ["stock-chart-bot", "--config", "/app/config.toml"]
