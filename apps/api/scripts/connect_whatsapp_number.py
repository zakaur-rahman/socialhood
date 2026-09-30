"""Development only: connect a WhatsApp number directly with a token, for a number Embedded Signup
can't connect, such as Meta's test number from the app's API Setup page (docs/dev-whatsapp.md).

    cd apps/api
    uv run python scripts/connect_whatsapp_number.py --workspace <slug or id> \\
        --waba-id <id> --phone-number-id <id>

The token comes from WHATSAPP_DEV_TOKEN, in the environment or apps/api/.env: a system user's
token, or API Setup's temporary one (it lasts about a day). It is never printed and never an
argument. The number takes the same path as Embedded Signup after its code exchange
(services/whatsapp_connect.py, connect_number): the plan limit, an active workspace,
account_in_use, the token encrypted, the app subscribed to the WhatsApp Business Account, and
registration with a PIN we keep. Meta refuses to register its test numbers; that is logged and
skipped, and the number still sends. Refused when APP_ENV is production.

Prints the account id, number and status, nothing secret. Exit code 1 when the connect is refused,
2 for a usage problem.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import selectors
import sys
import uuid
from collections.abc import Sequence
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.plans import current_plan
from socialhood.db.engine import make_engine, make_sessionmaker
from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ERROR_CODES, ApiError
from socialhood.jobs.runtime import make_http_client
from socialhood.models.connections import SocialAccount
from socialhood.models.identity import Workspace, WorkspaceStatus
from socialhood.observability.logging import configure_logging
from socialhood.platforms.deps import deps_from
from socialhood.platforms.whatsapp.signup import BusinessToken
from socialhood.services.whatsapp_connect import connect_number
from socialhood.settings import Settings, get_settings

API_ROOT = Path(__file__).resolve().parents[1]
TOKEN_ENV = "WHATSAPP_DEV_TOKEN"  # noqa: S105 (the variable's name, not a token)


class Refused(Exception):
    """A plain reason to stop before anything is stored."""


def dev_token() -> str | None:
    """WHATSAPP_DEV_TOKEN from the environment, else from apps/api/.env."""
    value = os.environ.get(TOKEN_ENV) or dotenv_values(API_ROOT / ".env").get(TOKEN_ENV)
    return value.strip() if value and value.strip() else None


def parse(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--workspace", required=True, help="the workspace's slug or id")
    parser.add_argument("--waba-id", required=True, help="the WhatsApp Business Account id")
    parser.add_argument("--phone-number-id", required=True, help="the phone number id")
    args = parser.parse_args(argv)
    for name in ("waba_id", "phone_number_id"):
        if not str(getattr(args, name)).isdigit():  # these go into Graph URL paths
            parser.error(f"--{name.replace('_', '-')} must be Meta's numeric id")
    return args


async def find_workspace(session: AsyncSession, ref: str) -> Workspace | None:
    """By id or slug. Workspaces are the tenants themselves, so no scope is needed."""
    try:
        condition = Workspace.id == uuid.UUID(ref)
    except ValueError:
        condition = Workspace.slug == ref
    return (await session.scalars(select(Workspace).where(condition))).one_or_none()


async def connect(
    settings: Settings, *, workspace: str, waba_id: str, phone_number_id: str, token: str
) -> SocialAccount:
    """Store the number in the workspace through connect_number. Raises Refused or ApiError."""
    if settings.is_production:
        raise Refused("This script is for development only; APP_ENV is production.")
    engine = make_engine(settings)
    try:
        async with make_http_client() as http, make_sessionmaker(engine)() as session:
            ws = await find_workspace(session, workspace)
            if ws is None:
                raise Refused(f"No workspace {workspace!r}.")
            if ws.status != WorkspaceStatus.ACTIVE:
                raise Refused(f"Workspace {ws.slug!r} isn't active.")
            with workspace_scope(ws.id):
                return await connect_number(
                    session,
                    deps_from(http, settings),
                    grant=BusinessToken(token, None),
                    waba_id=waba_id,
                    phone_number_id=phone_number_id,
                    workspace_id=ws.id,
                    user_id=ws.owner_user_id,
                    plan=await current_plan(session),
                )
    finally:
        await engine.dispose()


async def run(argv: Sequence[str] | None = None, *, settings: Settings | None = None) -> int:
    args = parse(argv)
    settings = settings or get_settings()
    token = dev_token()
    if token is None:
        print(f"Set {TOKEN_ENV} in apps/api/.env (docs/dev-whatsapp.md).", file=sys.stderr)
        return 2
    try:
        acct = await connect(
            settings,
            workspace=args.workspace,
            waba_id=args.waba_id,
            phone_number_id=args.phone_number_id,
            token=token,
        )
    except Refused as refused:
        print(refused, file=sys.stderr)
        return 2
    except ApiError as error:
        detail = error.detail or ERROR_CODES[error.code].title
        print(f"Not connected ({error.code}): {detail}", file=sys.stderr)
        return 1
    print(f"Connected WhatsApp account {acct.id}")
    print(f"  number: {acct.phone_number} ({acct.display_name})")
    print(f"  status: {acct.status}" + (f" ({acct.last_error})" if acct.last_error else ""))
    return 0


if __name__ == "__main__":
    os.chdir(API_ROOT)  # .env is read from here
    configure_logging("WARNING")  # a skipped registration or failed subscription shows
    sys.exit(
        asyncio.run(
            run(),
            loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
        )
    )
