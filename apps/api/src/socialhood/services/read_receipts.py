"""Read receipts to the platform (T3.6, TR-PL table): when a member opens a conversation, the
read API marks it read in our database and calls ``after_marked_read``, which enqueues the
platform "seen" call. The job sends it only for accounts with the read_receipts capability.
Read receipts are a courtesy: failures are logged, never shown to the user or retried."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.jobs.enqueue import enqueue
from socialhood.models.connections import AccountStatus
from socialhood.models.inbox import Conversation
from socialhood.observability.logging import get_logger
from socialhood.platforms.buckets import Bucket, TokenBuckets
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.registry import adapter_for
from socialhood.repositories import inbox
from socialhood.repositories import social_accounts as accounts

log = get_logger(__name__)


async def after_marked_read(session: AsyncSession, conv: Conversation) -> None:
    """Queue the platform "seen" call; one waiting job per conversation is enough."""
    from socialhood.jobs.tasks.send import mark_read

    try:
        await enqueue(
            mark_read,
            key=f"read:{conv.id}",
            conversation_id=str(conv.id),
            workspace_id=str(conv.workspace_id),
        )
    except Exception:
        log.warning("read_receipt_enqueue_failed", conversation_id=str(conv.id))


async def send_read_receipt(
    sessionmaker: async_sessionmaker[AsyncSession],
    deps: PlatformDeps,
    conversation_id: uuid.UUID,
    *,
    buckets: TokenBuckets | None = None,
) -> bool:
    """Tell the platform the conversation was seen. Runs in the conversation's workspace scope;
    returns whether the call was made and accepted."""
    async with sessionmaker() as session:
        conv = await inbox.get_conversation(session, conversation_id)
        if conv is None:
            return False
        acct = await accounts.get(session, conv.social_account_id)
        contact = await inbox.get_contact(session, conv.contact_id)
    if acct is None or contact is None or acct.status != AccountStatus.ACTIVE:
        return False
    try:
        adapter = adapter_for(acct, deps)
        if Capability.READ_RECEIPTS not in adapter.capabilities_for(acct):
            return False
        # Sender actions count against the Send API rate (TR-PL-09); if the bucket is empty,
        # skip rather than wait: the next open sends another.
        if buckets is not None and await _busy(buckets, acct.platform, acct.id):
            log.info("read_receipt_skipped", conversation_id=str(conversation_id), reason="rate")
            return False
        await adapter.mark_read(acct, contact.platform_user_id)
    except PlatformError as error:
        log.info(
            "read_receipt_failed",
            conversation_id=str(conversation_id),
            error_code=error.code,
            platform_code=error.platform_code,
        )
        return False
    return True


async def _busy(buckets: TokenBuckets, platform: str, account_id: uuid.UUID) -> bool:
    bucket = Bucket.WA_SEND if platform == "whatsapp" else Bucket.IG_SEND
    try:
        return await buckets.take(bucket, str(account_id)) > 0
    except Exception:
        return False
