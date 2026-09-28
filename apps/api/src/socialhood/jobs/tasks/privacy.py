"""Meta data-deletion requests (F-16): disconnect the accounts and delete what we hold for them."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.app import BULK, app
from socialhood.jobs.runtime import runtime
from socialhood.models.platform import DeletionStatus
from socialhood.repositories import data_deletion, webhook_events
from socialhood.repositories import social_accounts as accounts
from socialhood.services.connections import mark_disconnected_by_platform
from socialhood.webhooks.routing import accounts_for_platform_user


async def delete_user_data(
    sessionmaker: async_sessionmaker[AsyncSession], confirmation_code: str
) -> bool:
    async with sessionmaker() as session:
        request = await data_deletion.get_by_code(session, confirmation_code)
        if request is None or request.status == DeletionStatus.COMPLETED:
            return False
        user_id = request.platform_user_id
        await data_deletion.set_status(session, confirmation_code, DeletionStatus.PROCESSING)
        await session.commit()

        for routed in await accounts_for_platform_user(session, user_id):
            with workspace_scope(routed.workspace_id):
                acct = await accounts.get(session, routed.account_id)
                if acct is None:
                    continue
                await mark_disconnected_by_platform(session, acct)
                # Raw webhook payloads for this account; inbox and comment data join in P3 and P6.
                await webhook_events.delete_for_account(session, acct.platform_account_id)
                await session.commit()

        await data_deletion.set_status(session, confirmation_code, DeletionStatus.COMPLETED)
        await session.commit()
    return True


@app.task(name="delete_platform_user_data", queue=BULK)
async def delete_platform_user_data(confirmation_code: str) -> None:
    await delete_user_data(runtime().sessionmaker, confirmation_code)
