"""Operators: block or unblock one AI app (an OAuth client) for every workspace, the per-client
block list of docs/architecture/mcp/01-design.md §6.7.

    cd apps/api
    uv run python scripts/block_oauth_client.py block <client_id>
    uv run python scripts/block_oauth_client.py unblock <client_id>

``client_id`` is what the app sends to /oauth/authorize: its metadata document's URL, or the
``dcr_…`` id it got when it registered. A blocked client is refused at /oauth/authorize,
/oauth/token and /oauth/revoke, its tokens are refused on /mcp, and the nightly cleanup never
removes its row. Blocking also revokes the client's live connections in every workspace, so
unblocking brings none of them back: members connect again.

Prints the client's name and how many connections were revoked. Exit code 2 when there is no
such client.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.engine import make_engine, make_sessionmaker
from socialhood.db.tenancy import tenant_bypass_scope
from socialhood.models.oauth import McpConnection, RevokeReason
from socialhood.oauth.clients import find_client
from socialhood.oauth.service import revoke_connection
from socialhood.settings import Settings, get_settings


def parse(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("action", choices=("block", "unblock"))
    parser.add_argument("client_id", help="the client's metadata document URL or its dcr_ id")
    return parser.parse_args(argv)


async def set_blocked(
    sessionmaker: async_sessionmaker[AsyncSession], client_id: str, *, blocked: bool, now: datetime
) -> tuple[str, int] | None:
    """Block or unblock the client; its name and how many connections were revoked, or None when
    there is no such client. Blocking one that is blocked keeps its first time."""
    async with sessionmaker() as session:
        client = await find_client(session, client_id)
        if client is None:
            return None
        revoked = 0
        if blocked:
            client.blocked_at = client.blocked_at or now
            with tenant_bypass_scope():  # one client's connections, in every workspace
                live = await session.scalars(
                    select(McpConnection).where(
                        McpConnection.oauth_client_id == client.id,
                        McpConnection.revoked_at.is_(None),
                    )
                )
                # shortcut: recorded as reason "all" with no member (a reason of its own needs a
                # migration, the column has a CHECK), add "blocked" with the next migration.
                revoked = sum(revoke_connection(c, RevokeReason.ALL, now) for c in live.all())
        else:
            client.blocked_at = None
        await session.commit()
        return client.client_name, revoked


async def run(argv: Sequence[str] | None = None, *, settings: Settings | None = None) -> int:
    args = parse(argv)
    engine = make_engine(settings or get_settings())
    try:
        done = await set_blocked(
            make_sessionmaker(engine),
            args.client_id,
            blocked=args.action == "block",
            now=datetime.now(UTC),
        )
    finally:
        await engine.dispose()
    if done is None:
        print(f"No client {args.client_id!r}.", file=sys.stderr)
        return 2
    name, revoked = done
    if args.action == "block":
        print(f"Blocked {name!r}. Connections revoked: {revoked}.")
    else:
        print(f"Unblocked {name!r}. Its old connections stay revoked.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
