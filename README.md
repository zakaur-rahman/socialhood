# Social Hood

One inbox for Instagram and WhatsApp, with AI that answers from a business's own knowledge.

The build spec is in [`docs/`](docs/): `BUILD_SPEC.html` (PRD, TRD, flows, UX, schema, plan),
the architecture review and the Instagram requirements. Work follows the plan in its §6;
questions and spec conflicts go in `docs/QUESTIONS.md` and `docs/CONFLICTS.md`.

## Layout

| Path | What |
|------|------|
| `apps/api` | FastAPI API and the job worker: one Python package, `socialhood` |
| `apps/web` | Next.js app |
| `packages/api-client` | TypeScript types generated from the API's OpenAPI document |
| `infra` | Local services (`docker-compose.yml`) |
| `docs` | Spec, questions, conflicts, platform verification |

## Prerequisites

Docker, Node 22 or newer, pnpm 9, and [uv](https://docs.astral.sh/uv/) (it installs Python 3.13).

## Setup

```sh
docker compose -f infra/docker-compose.yml up -d     # Postgres 18 + pgvector, Valkey 8
pnpm install

cd apps/api
cp .env.example .env
uv sync
uv run alembic upgrade head
```

## Run

```sh
# API on http://localhost:8000 (docs at /docs outside production)
cd apps/api && uv run uvicorn socialhood.main:app --reload --port 8000 --no-access-log
# Windows: add --loop asyncio:SelectorEventLoop (the job queue's driver needs it; see QUESTIONS Q-006)

# Worker. Linux and macOS: one process per lane, as in production
cd apps/api && ./scripts/worker.sh
# Windows: a single worker for both lanes
cd apps/api && uv run procrastinate --app=socialhood.jobs.app.app worker

# Web on http://localhost:3000 (design tokens at /dev/tokens)
cd apps/web && cp .env.example .env.local && pnpm dev
```

## Checks (all must pass before merge, §6.1)

```sh
cd apps/api
uv run ruff format --check . && uv run ruff check . && uv run mypy
uv run python scripts/check_tenancy.py      # TR-TEN-04
uv run pytest                               # uses socialhood_test and Valkey db 15

cd ../web
pnpm lint && pnpm typecheck && pnpm test && pnpm build

cd ../..
pnpm gen:api                                # regenerate the API contract; commit any change
```

If `uv` is not on your PATH, set `UV` to its full path for `pnpm gen:api`.
