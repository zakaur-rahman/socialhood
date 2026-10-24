"""The public pages' plan table is a copy of billing/plans.py; this test keeps it honest (GR-37).

apps/web/src/lib/marketing/plan-table.json holds every entitlement per plan, as exported from
`ENTITLEMENTS` and `TRIAL_DAYS`. The pricing page's comparison table (lib/marketing/plan-matrix.ts)
reads that file, and a web test checks that every row it shows exists there, so a number can't be
edited in one place and forgotten in the other. After changing billing/plans.py, run

    UPDATE_PLAN_TABLE=1 uv run pytest tests/unit/test_marketing_plan_table.py

to rewrite the file, then review the diff and the pricing page's wording.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from socialhood.billing.plans import ENTITLEMENTS, PLANS, TRIAL_DAYS

TABLE = (
    Path(__file__).resolve().parents[3] / "web" / "src" / "lib" / "marketing" / "plan-table.json"
)


def exported() -> dict[str, Any]:
    """The plan table as JSON: a tuple (ai_modes) becomes a list, None (unlimited) becomes null."""
    return {
        "plans": list(PLANS),
        "trial_days": dict(TRIAL_DAYS),
        "entitlements": {
            key: {
                plan: list(value) if isinstance(value, tuple) else value
                for plan, value in by_plan.items()
            }
            for key, by_plan in ENTITLEMENTS.items()
        },
    }


def test_the_pricing_pages_plan_table_matches_billing_plans() -> None:
    if os.environ.get("UPDATE_PLAN_TABLE"):
        TABLE.write_text(json.dumps(exported(), indent=2) + "\n", encoding="utf-8")
    assert json.loads(TABLE.read_text(encoding="utf-8")) == exported(), (
        "billing/plans.py changed: run UPDATE_PLAN_TABLE=1 uv run pytest "
        "tests/unit/test_marketing_plan_table.py to rewrite plan-table.json in the web app"
    )
