"""The email outbox (T8.5; FR-NOT-02, FR-NOT-04): queue in the caller's transaction, send in a job.

- ``queue_email`` inserts an email_deliveries row (status queued) unless one with the same
  (workspace, dedupe_key) exists, and returns its id or None. It runs in the same transaction as
  what caused it (a notification row, a digest), so an email exists exactly when its cause does,
  and it records deliver_email (key ``email:{id}``) to be deferred when that transaction commits
  (notify/dispatch.py). sweep_email_outbox re-enqueues rows still queued a minute after they were
  created, so a lost enqueue only delays an email; a row still queued after a day fails instead
  of arriving late.
- ``send_queued`` locks the row for the send (FOR UPDATE SKIP LOCKED: a second job for the same
  row finds it locked and does nothing), checks it should still go, renders the template
  (notify/templates/), sends with ``{workspace_id}:{dedupe_key}`` as the Idempotency-Key (Resend
  keys are account-wide, and a digest's dedupe key repeats across workspaces), and records sent
  (provider id, sent_at; the notification's emailed_at), failed, or skipped. The ``sending``
  state is never committed: a worker that dies mid-send rolls back to queued, and the resend
  carries the same Idempotency-Key, so Resend delivers it once.
- Retries: a retryable EmailError (timeout, 429, 5xx) with attempts left puts the row back to
  queued with the error and re-raises, so the job retries with backoff; the last attempt, or a
  refusal, marks it failed. Never "failed, then re-raise" (TR-JOB-04).
- Skipped: the recipient's user is gone or no longer a member of the workspace, the address is
  empty, or (the digest) the member turned it off since it was queued.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import require_workspace
from socialhood.models.notifications import EmailDelivery, EmailStatus, EmailTemplate
from socialhood.notify import dispatch, preferences
from socialhood.notify.email import EmailError, EmailMessage, EmailSender
from socialhood.notify.templates import render
from socialhood.notify.unsubscribe import make_token
from socialhood.observability.logging import get_logger
from socialhood.repositories import email_deliveries as repo
from socialhood.settings import Settings

log = get_logger(__name__)

MAX_ATTEMPTS = 5  # the job catalogue's deliver_email: 5 tries
ERROR_CHARS = 500


def idempotency_key(delivery: EmailDelivery) -> str:
    return f"{delivery.workspace_id}:{delivery.dedupe_key}"


def unsubscribe_links(
    settings: Settings, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[str, dict[str, str]]:
    """The digest's unsubscribe page link and its RFC 8058 headers. The header points at the
    API's POST /v1/digest/unsubscribe (one click from the mail client); the link in the body
    opens the web page, which posts there, so a link scanner's GET unsubscribes nobody."""
    token = make_token(workspace_id, user_id, settings.token_encryption_keys)
    page = f"{(settings.web_base_url or '').rstrip('/')}/unsubscribe?token={token}"
    headers: dict[str, str] = {}
    if settings.api_base_url:
        endpoint = f"{settings.api_base_url.rstrip('/')}/v1/digest/unsubscribe?token={token}"
        headers = {
            "List-Unsubscribe": f"<{endpoint}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }
    return page, headers


async def queue_email(
    session: AsyncSession,
    *,
    template: str,
    to_email: str,
    dedupe_key: str,
    data: Mapping[str, Any],
    user_id: uuid.UUID | None = None,
    notification_id: uuid.UUID | None = None,
) -> uuid.UUID | None:
    """Queue one email in the current workspace; None when its dedupe key was queued before."""
    EmailTemplate(template)  # ValueError for a template that doesn't exist
    workspace_id = require_workspace()
    delivery_id = await repo.insert_queued(
        session,
        {
            "template": template,
            "to_email": to_email,
            "dedupe_key": dedupe_key,
            "data": dict(data),
            "user_id": user_id,
            "notification_id": notification_id,
        },
    )
    if delivery_id is not None:
        dispatch.after_commit(session, "deliver_email", delivery_id, workspace_id)
    return delivery_id


async def _skip_reason(session: AsyncSession, row: EmailDelivery) -> str | None:
    if not row.to_email.strip():
        return "No email address"
    if row.user_id is None:
        return "The recipient's account was deleted"
    member = await preferences.member(session, row.user_id)
    if member is None:
        return "The recipient is no longer a member of the workspace"
    if row.template == EmailTemplate.WEEKLY_DIGEST and not preferences.wants_digest(
        member.notification_prefs
    ):
        return "The member turned the weekly digest off"
    return None


def build_message(row: EmailDelivery, settings: Settings) -> EmailMessage:
    """Render the row's email. ``ValueError`` for an unknown template or missing WEB_BASE_URL."""
    if not settings.web_base_url:
        raise ValueError("WEB_BASE_URL is not set, so email links can't be written")
    data: dict[str, Any] = dict(row.data or {})
    headers: dict[str, str] = {}
    if row.template == EmailTemplate.WEEKLY_DIGEST and row.user_id is not None:
        data["unsubscribe_url"], headers = unsubscribe_links(
            settings, row.workspace_id, row.user_id
        )
    rendered = render(row.template, data, web_base_url=settings.web_base_url)
    return EmailMessage(
        to=row.to_email,
        subject=rendered.subject,
        html=rendered.html,
        text=rendered.text,
        idempotency_key=idempotency_key(row),
        headers=headers,
        tags={"template": row.template},
    )


async def send_queued(
    sessionmaker: async_sessionmaker[AsyncSession],
    delivery_id: uuid.UUID,
    *,
    sender: EmailSender,
    settings: Settings,
    will_retry: Callable[[EmailError], bool] | None = None,
    now: datetime | None = None,
) -> str:
    """Send one queued email in the current workspace; returns its final status (``missing``
    when the row doesn't exist or another sender holds it). ``will_retry`` says whether the job
    will run again after this error; without it the row's attempt count alone decides."""
    async with sessionmaker() as session:
        row = await repo.lock_for_send(session, delivery_id)
        if row is None:
            return "missing"
        if row.status != EmailStatus.QUEUED:
            return row.status
        if (reason := await _skip_reason(session, row)) is not None:
            row.status, row.error = EmailStatus.SKIPPED, reason
            await session.commit()
            log.info("email_skipped", delivery_id=str(row.id), template=row.template)
            return EmailStatus.SKIPPED
        try:
            message = build_message(row, settings)
        except Exception as error:  # a template or configuration bug: retrying won't fix it
            row.status, row.error = EmailStatus.FAILED, f"Couldn't render: {error}"[:ERROR_CHARS]
            await session.commit()
            log.error("email_render_failed", delivery_id=str(row.id), template=row.template)
            return EmailStatus.FAILED
        row.subject = message.subject
        row.attempts += 1
        try:
            sent = await sender.send(message)
        except EmailError as error:
            retry = (
                error.retryable
                and row.attempts < MAX_ATTEMPTS
                and (will_retry is None or will_retry(error))
            )
            row.status = EmailStatus.QUEUED if retry else EmailStatus.FAILED
            row.error = str(error)[:ERROR_CHARS]
            await session.commit()
            log.warning(
                "email_send_failed",
                delivery_id=str(delivery_id),
                template=message.tags.get("template"),
                status=error.status,
                attempt=row.attempts,
                retry=retry,
            )
            if retry:
                raise
            return EmailStatus.FAILED
        at = now or datetime.now(UTC)
        row.status, row.error = EmailStatus.SENT, None
        row.provider_message_id, row.sent_at = sent.provider_message_id, at
        if row.notification_id is not None:
            await repo.mark_notification_emailed(session, row.notification_id, at)
        await session.commit()
    log.info("email_sent", delivery_id=str(delivery_id), template=message.tags.get("template"))
    return EmailStatus.SENT
