# syntax=docker/dockerfile:1.7
# The API image (C-145): one image, three commands.
#   API (default):  uvicorn socialhood.main:app ... (CMD below; compose sets FORWARDED_ALLOW_IPS)
#   Worker:         bash scripts/worker.sh
#   Migrations:     alembic upgrade head
# Build from apps/api:  docker build -t amplychat-api apps/api
# Nothing secret is baked in: every setting comes from the environment at run time.

ARG PYTHON_VERSION=3.13

# ---- builder: resolve the locked dependencies into /app/.venv with uv
FROM python:${PYTHON_VERSION}-slim-trixie AS builder
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python${PYTHON_VERSION} \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
# Dependencies first (cached until uv.lock changes), then the project itself.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# ---- runtime: the virtualenv, the migrations and the worker script; no uv, no compilers
FROM python:${PYTHON_VERSION}-slim-trixie AS runtime
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --no-create-home app
# Trixie's tzdata leaves out the legacy zone names (Asia/Calcutta, US/Eastern…) that browsers still
# report from Intl; without them a workspace's timezone is refused (C-151). tzdata-legacy adds them.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata-legacy \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
# Fail the build if the zone names the browsers send aren't known (C-151).
RUN python -c "from zoneinfo import available_timezones as a; z = a(); assert {'Asia/Kolkata', 'Asia/Calcutta', 'US/Eastern', 'Europe/Kiev'} <= z, 'legacy timezones missing'"
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts/worker.sh ./scripts/worker.sh
USER app
EXPOSE 8000
# /healthz says only that the process is up (api/health.py); the worker overrides this check.
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"]
# As infra/render.yaml: --no-server-header (SEC-11), no access log (Caddy keeps one).
# --proxy-headers takes the scheme from Caddy; uvicorn trusts the forwarded headers only from
# FORWARDED_ALLOW_IPS (compose: Caddy's fixed address). Rate limits read CLIENT_IP_HEADER.
CMD ["uvicorn", "socialhood.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--no-server-header", "--no-access-log", \
     "--timeout-graceful-shutdown", "20"]
