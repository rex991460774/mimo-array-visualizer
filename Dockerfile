# syntax=docker/dockerfile:1

# ── Stage 1: build the web client ────────────────────────────────────
FROM node:22-bookworm-slim AS web
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npx tsc -b && npx vite build --outDir /build/static --emptyOutDir

# ── Stage 2: Python server ───────────────────────────────────────────
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MPLBACKEND=Agg \
    MALLOC_ARENA_MAX=2 \
    MIMO_DATA_DIR=/data

# CJK fonts are required for Chinese/Japanese PDF reports.  They must be
# installed before matplotlib builds its font cache.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY --from=web /build/static ./src/virtual_array/server/static
RUN pip install . \
    && useradd --create-home --uid 1000 mimo \
    && mkdir -p /data \
    && chown mimo:mimo /data

USER mimo
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"
CMD ["mimo-array-server", "--host", "0.0.0.0", "--port", "8000", "--data-dir", "/data"]
