"""One-off at go-live (docs/ops/deploy-vm.md, "Going live with Dodo"): paid plans whose subscription
only exists in Dodo's test mode move to Free, with the usual downgrade effects and notification.

    python -m socialhood.billing.reset_test_plans           # lists them, changes nothing
    python -m socialhood.billing.reset_test_plans --apply

Run it after the live key is in place. It asks Dodo about every paid workspace and touches only
those Dodo answers "not found" for, so a real subscription stays as it is and running it twice is
safe. It stops if the key can't read one of our products: then every answer would be wrong.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime

from socialhood.billing import lifecycle
from socialhood.billing.dodo import DodoError
from socialhood.billing.reconcile import dodo_key_works
from socialhood.billing.registry import get_dodo
from socialhood.db.engine import make_engine, make_sessionmaker
from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.runtime import make_http_client
from socialhood.jobs.tasks.billing import _paid_workspaces
from socialhood.repositories import subscriptions
from socialhood.settings import get_settings


async def run(*, apply: bool) -> int:
    settings = get_settings()
    engine = make_engine(settings)
    maker = make_sessionmaker(engine)
    try:
        async with make_http_client() as http:
            dodo = get_dodo(http, settings)
            if not await dodo_key_works(dodo, settings):
                print("Stopped: this Dodo key can't read our Creator product. Check the key.")
                return 1
            async with maker() as session:
                paid = await _paid_workspaces(session)
            found = unsure = 0
            for workspace_id in paid:
                with workspace_scope(workspace_id):
                    async with maker() as session:
                        sub = await subscriptions.current(session)
                        if sub is None or not sub.dodo_subscription_id:
                            print(f"{workspace_id}: paid with no Dodo id; left for a person")
                            unsure += 1
                            continue
                        try:
                            await dodo.get_subscription(sub.dodo_subscription_id)
                            continue
                        except DodoError as error:
                            if not error.not_found:
                                print(f"{workspace_id}: Dodo didn't answer; run this again")
                                unsure += 1
                                continue
                        found += 1
                        print(f"{workspace_id}: {sub.plan}, {sub.dodo_subscription_id} not in Dodo")
                        if apply:
                            await lifecycle.expire_now(
                                session, now=datetime.now(UTC), reason="test-mode subscription"
                            )
                            await session.commit()
    finally:
        await engine.dispose()
    verb = "Moved to Free" if apply else "Would move to Free"
    print(f"{verb}: {found} of {len(paid)} paid workspaces. Not decided: {unsure}.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run(apply="--apply" in sys.argv[1:])))
