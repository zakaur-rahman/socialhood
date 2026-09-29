"""Ask Social Hood's eval (TA.6; agent-architecture.html §18): seed the eval database fresh, run
every case in tests/evals/cases.py through the real orchestrator with the real Gemini planner,
check the answers and write a JSON and a markdown report to tests/evals/results/.

    cd apps/api
    TEST_DATABASE_URL=postgresql+asyncpg://…/socialhood_test_3 TEST_REDIS_URL=redis://…/12 \
        uv run python scripts/agent_eval.py [--only id,id] [--area inbox] [--delay 2] [--label v1]

The database comes from EVAL_DATABASE_URL, else TEST_DATABASE_URL (the tests' own), and must be
a test or eval database: the eval empties it. Valkey from EVAL_REDIS_URL, else TEST_REDIS_URL.
The Gemini key and models come from .env. It calls the model: expect about 3 credits and a few
seconds per case, one case at a time with a pause between them.

Targets (TA.6): tool choice at least 90%, every expected number in the answer, no number the
tools didn't return. The exit code is 1 when a target is missed.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import selectors
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = "postgresql+asyncpg://socialhood:socialhood@localhost:5432/socialhood_test"
DEFAULT_REDIS = "redis://localhost:6379/15"


def configure() -> None:
    """Point the settings at the eval database before anything reads them."""
    url = os.environ.get("EVAL_DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    url = url or DEFAULT_DATABASE
    name = url.rsplit("/", 1)[-1].split("?")[0]
    if "test" not in name and "eval" not in name:
        sys.exit(f"Refusing to empty {name!r}: use a test or eval database.")
    direct = os.environ.get("EVAL_DATABASE_URL_DIRECT") or os.environ.get(
        "TEST_DATABASE_URL_DIRECT"
    )
    os.environ["DATABASE_URL"] = url
    os.environ["DATABASE_URL_DIRECT"] = direct or url.replace("+asyncpg", "")
    os.environ["REDIS_URL"] = (
        os.environ.get("EVAL_REDIS_URL") or os.environ.get("TEST_REDIS_URL") or DEFAULT_REDIS
    )
    # Deterministic runs: no Human Agent window, the Gemini provider, and the retrieval
    # threshold for the bag-of-words embeddings the seed uses (tests/evals/runner.py).
    os.environ["IG_HUMAN_AGENT_ENABLED"] = "false"
    os.environ["AI_PROVIDER"] = "gemini"
    from tests.evals.runner import EVAL_RETRIEVAL_MIN_SIM

    from socialhood.settings import get_settings

    os.environ["AI_RETRIEVAL_MIN_SIM"] = EVAL_RETRIEVAL_MIN_SIM
    get_settings.cache_clear()  # an import may have read them already


def migrate() -> None:
    from alembic import command
    from alembic.config import Config

    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    command.upgrade(config, "head")


async def main(args: argparse.Namespace) -> int:
    import pydantic_ai.models
    from tests.evals.cases import CASES
    from tests.evals.runner import run_eval

    from socialhood.settings import get_settings

    # Tests forbid model requests; the eval exists to make them.
    pydantic_ai.models.ALLOW_MODEL_REQUESTS = True
    cases = list(CASES)
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c.id in wanted]
    if args.area:
        cases = [c for c in cases if c.area == args.area]
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        print("No cases match.")
        return 1
    settings = get_settings()
    summary, _ = await run_eval(settings, cases=cases, delay_s=args.delay, label=args.label)
    return 0 if all(summary.meets_targets().values()) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", help="comma-separated case ids")
    parser.add_argument("--area", help="one area: inbox, drafts, comments, posts, …")
    parser.add_argument("--limit", type=int, help="the first N cases")
    parser.add_argument("--delay", type=float, default=2.0, help="seconds between cases")
    parser.add_argument("--label", default="eval", help="a name for the reports")
    parser.add_argument("--no-migrate", action="store_true")
    parsed = parser.parse_args()
    os.chdir(API_ROOT)  # .env is read from here
    sys.path.insert(0, str(API_ROOT))
    if hasattr(sys.stdout, "reconfigure"):  # answers are Hindi too; progress shows as it goes
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    configure()
    if not parsed.no_migrate:
        migrate()
    sys.exit(
        asyncio.run(
            main(parsed),
            loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
        )
    )
