"""The Activity feed (GR-05): automation runs, failed flow steps, failed sends, failed outbound
webhook deliveries and accounts that need attention, merged newest first.

- Each source is read newest first with the same keyset, (time, id) after the cursor, and
  the merge keeps the newest ``limit``; the cursor is the last item's time and id, so paging never
  repeats or skips an item (ids are unique across tables).
- A failed send of an automation run is shown once, as the run (the run mirrors its message);
  a flow step is listed only when its run is not itself a failure. The Activity page lists the
  rest of the failed sends, human and AI ones.
- Every item has a plain reason and at most one action (services/activity/reasons.py), and says
  whether a retry is safe: a message that failed with "not now" codes (re-sent through the
  existing retry route) or a failed webhook delivery to an endpoint that is on (the replay route).
- Raw payloads, message text and the platform's raw responses are never returned. The page is
  for owners and admins (it names contacts and endpoints), like the automations it reports on.
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError
from socialhood.models.automations import RunResult
from socialhood.models.connections import AccountStatus
from socialhood.models.integrations import EndpointStatus
from socialhood.repositories import activity as repo
from socialhood.schemas.activity import (
    ActivityAction,
    ActivityItem,
    ActivityKindName,
    ActivityList,
    ActivityOutcome,
    ActivityRetry,
)
from socialhood.services.activity import reasons
from socialhood.services.automations.results import PRIVATE_PREFIX, PUBLIC_PREFIX
from socialhood.services.sending import platform_name

Kind = Literal["automation_run", "flow_step", "message", "webhook_delivery", "account"]

# What a run that is not a failure did, for its title.
RUN_VERBS: dict[str, str] = {
    RunResult.SENT: "replied",
    RunResult.QUEUED: "has a reply waiting to go out",
    RunResult.AWAITING_REPLY: "is waiting for an answer",
    RunResult.ESCALATED: "handed a conversation to your team",
    RunResult.SKIPPED_COOLDOWN: "skipped someone it already replied to",
}
RUN_OUTCOME: dict[str, ActivityOutcome] = {
    RunResult.FAILED: "failed",
    RunResult.PARTIAL: "partial",
    RunResult.SKIPPED_EXPIRED: "skipped",
    RunResult.SKIPPED_READ_ONLY: "skipped",
    RunResult.SKIPPED_COOLDOWN: "skipped",
}
SOURCE_LABELS = {
    "automation": "An automation message",
    "ai_auto": "An AI reply",
    "human": "A message",
}
REASON_MAX = 400


def href_for(
    target: reasons.Target | None,
    *,
    conversation_id: uuid.UUID | None = None,
    automation_id: uuid.UUID | None = None,
) -> str | None:
    """The link inside the workspace for an action's target (the web adds /w/{slug})."""
    if target == "connections":
        return "/settings/connections"
    if target == "billing":
        return "/settings/billing"
    if target == "integrations":
        return "/settings/integrations"
    if target == "conversation" and conversation_id is not None:
        return f"/inbox/{conversation_id}"
    if target == "automation" and automation_id is not None:
        return f"/automations/{automation_id}"
    return None


def _action(
    reason: reasons.Reason,
    *,
    conversation_id: uuid.UUID | None = None,
    automation_id: uuid.UUID | None = None,
) -> ActivityAction | None:
    href = href_for(reason.target, conversation_id=conversation_id, automation_id=automation_id)
    if reason.label is None or href is None:
        return None
    return ActivityAction(label=reason.label, href=href)


def account_label(
    username: str | None, display_name: str | None, platform: str | None
) -> str | None:
    if username:
        return f"@{username}"
    if display_name:
        return display_name
    return platform_name(platform) if platform else None


def _who(username: str | None, display_name: str | None) -> str | None:
    if username:
        return f"@{username}"
    return display_name or None


def _to(who: str | None) -> str:
    return f" to {who}" if who else ""


def _clip(text: str | None) -> str | None:
    if not text:
        return None
    return text if len(text) <= REASON_MAX else text[: REASON_MAX - 1].rstrip() + "..."


def _run_reason(row: Any) -> reasons.Reason:
    reason = reasons.explain(
        _run_code(row),
        stored=row.error_message,
        platform=row.platform,
        username=row.account_username,
        has_conversation=row.conversation_id is not None,
        has_automation=True,
    )
    stored = row.error_message or ""
    if stored.startswith((PUBLIC_PREFIX, PRIVATE_PREFIX)):
        # A comment run keeps which part failed ("Public reply: ... DM: ..."): say it as stored.
        return reasons.Reason(stored, reason.code, reason.label, reason.target)
    return reason


def _run_code(row: Any) -> str | None:
    if row.result == RunResult.SKIPPED_EXPIRED:
        return reasons.LIVE_ENDED if row.error_code == reasons.LIVE_ENDED else reasons.EXPIRED
    if row.result == RunResult.SKIPPED_READ_ONLY:
        return reasons.READ_ONLY
    code: str | None = row.error_code
    return code


def _run_item(row: Any) -> ActivityItem:
    outcome = RUN_OUTCOME.get(row.result, "ok")
    who = _who(row.contact_username, row.contact_display_name)
    reason: reasons.Reason | None = None
    if outcome in ("failed", "partial") or row.result in (
        RunResult.SKIPPED_EXPIRED,
        RunResult.SKIPPED_READ_ONLY,
    ):
        reason = _run_reason(row)
    if row.result == RunResult.FAILED:
        title = f"{row.automation_name} couldn't reply{_to(who)}"
    elif row.result == RunResult.PARTIAL:
        title = f"{row.automation_name} replied in part{_to(who)}"
    elif row.result == RunResult.SKIPPED_EXPIRED and row.error_code == reasons.LIVE_ENDED:
        title = f"{row.automation_name} skipped a comment that came after the Live ended"
    elif row.result == RunResult.SKIPPED_EXPIRED:
        title = f"{row.automation_name} skipped a comment that was too old"
    elif row.result == RunResult.SKIPPED_READ_ONLY:
        title = f"{row.automation_name} didn't send because the account is read-only"
    else:
        title = f"{row.automation_name} {RUN_VERBS.get(row.result, 'ran')}{_to(who)}"
    return ActivityItem(
        id=row.id,
        kind="automation_run",
        outcome=outcome,
        occurred_at=row.at,
        title=title,
        reason=_clip(reason.text) if reason else None,
        error_code=reason.code if reason else None,
        automation_id=row.automation_id,
        automation_name=row.automation_name,
        social_account_id=row.account_id,
        account_label=account_label(row.account_username, row.account_display_name, row.platform),
        platform=row.platform,
        action=_action(reason, conversation_id=row.conversation_id, automation_id=row.automation_id)
        if reason
        else None,
    )


def _step_item(row: Any) -> ActivityItem:
    detail = row.detail or {}
    reason = reasons.explain(
        detail.get("error_code"),
        stored=detail.get("error"),
        platform=row.platform,
        username=row.account_username,
        has_conversation=row.conversation_id is not None,
        has_automation=True,
    )
    who = _who(row.contact_username, row.contact_display_name)
    return ActivityItem(
        id=row.id,
        kind="flow_step",
        outcome="failed",
        occurred_at=row.at,
        title=f"{row.automation_name} couldn't send a message{_to(who)}",
        reason=_clip(reason.text),
        error_code=reason.code,
        automation_id=row.automation_id,
        automation_name=row.automation_name,
        social_account_id=row.account_id,
        account_label=account_label(row.account_username, row.account_display_name, row.platform),
        platform=row.platform,
        action=_action(
            reason, conversation_id=row.conversation_id, automation_id=row.automation_id
        ),
    )


def _message_item(row: Any) -> ActivityItem:
    reason = reasons.explain(
        row.error_code,
        stored=row.error_message,
        platform=row.platform,
        username=row.account_username,
        has_conversation=True,
    )
    who = _who(row.contact_username, row.contact_display_name)
    retryable = reasons.message_retryable(row.error_code)
    label = SOURCE_LABELS.get(row.source, "A message")
    return ActivityItem(
        id=row.id,
        kind="message",
        outcome="failed",
        occurred_at=row.at,
        title=f"{label}{_to(who)} wasn't sent",
        reason=_clip(reason.text),
        error_code=reason.code,
        social_account_id=row.account_id,
        account_label=account_label(row.account_username, row.account_display_name, row.platform),
        platform=row.platform,
        action=_action(reason, conversation_id=row.conversation_id),
        retryable=retryable,
        retry=ActivityRetry(kind="message", target_id=row.id) if retryable else None,
    )


def _endpoint_name(row: Any) -> str:
    if row.endpoint_description:
        return str(row.endpoint_description)
    return urlsplit(row.endpoint_url).hostname or "your endpoint"


def _delivery_item(row: Any) -> ActivityItem:
    code = reasons.webhook_code(error=row.error, response_code=row.response_code)
    reason = reasons.explain(code, stored=row.error)
    # A replay needs the endpoint on (services/webhooks/endpoints.replay).
    retryable = row.endpoint_status == EndpointStatus.ACTIVE
    return ActivityItem(
        id=row.id,
        kind="webhook_delivery",
        outcome="failed",
        occurred_at=row.at,
        title=f"A {row.event_type} event wasn't delivered to {_endpoint_name(row)}",
        reason=_clip(reason.text),
        error_code=reason.code,
        action=_action(reason),
        retryable=retryable,
        retry=ActivityRetry(kind="webhook_delivery", target_id=row.id) if retryable else None,
    )


def _account_item(row: Any) -> ActivityItem:
    label = account_label(row.account_username, row.account_display_name, row.platform)
    if row.status == AccountStatus.NEEDS_RECONNECT:
        reason = reasons.explain(
            "account_needs_reconnect",
            stored=row.last_error,
            platform=row.platform,
            username=row.account_username,
        )
        title = f"{label} needs reconnecting"
    else:
        reason = reasons.explain(
            "capability_unavailable",
            stored=row.last_error,
            platform=row.platform,
            username=row.account_username,
        )
        title = f"{label} has a connection problem"
    # The stored line is the plain-language reason the connection code wrote (F-05).
    text = row.last_error or reason.text
    return ActivityItem(
        id=row.id,
        kind="account",
        outcome="attention",
        occurred_at=row.at,
        title=title,
        reason=_clip(text),
        error_code=reason.code,
        social_account_id=row.id,
        account_label=label,
        platform=row.platform,
        action=_action(reason),
    )


def encode_cursor(at: datetime, row_id: uuid.UUID) -> str:
    raw = json.dumps([at.isoformat(), str(row_id)]).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def decode_cursor(cursor: str) -> repo.Before:
    try:
        at, row_id = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        return datetime.fromisoformat(at), uuid.UUID(row_id)
    except (ValueError, TypeError) as error:
        raise ApiError("bad_request", "That page link isn't valid any more.") from error


async def feed(
    session: AsyncSession,
    *,
    failures_only: bool,
    kind: Kind | None,
    automation_id: uuid.UUID | None,
    account_id: uuid.UUID | None,
    cursor: str | None,
    limit: int,
) -> ActivityList:
    """The newest ``limit`` items. A filter on an automation leaves out the sources that have
    none (sends, webhooks, accounts); a filter on an account leaves out webhooks."""
    before = decode_cursor(cursor) if cursor else None
    take = limit + 1
    wanted: set[ActivityKindName] = (
        {kind}
        if kind
        else {"automation_run", "flow_step", "message", "webhook_delivery", "account"}
    )
    if automation_id is not None:
        wanted &= {"automation_run", "flow_step"}
    if account_id is not None:
        wanted -= {"webhook_delivery"}
    items: list[ActivityItem] = []
    if "automation_run" in wanted:
        rows = await repo.runs(
            session,
            before=before,
            limit=take,
            failures_only=failures_only,
            automation_id=automation_id,
            account_id=account_id,
        )
        items += [_run_item(r) for r in rows]
    if "flow_step" in wanted:
        rows = await repo.failed_steps(
            session, before=before, limit=take, automation_id=automation_id, account_id=account_id
        )
        items += [_step_item(r) for r in rows]
    if "message" in wanted:
        rows = await repo.failed_messages(session, before=before, limit=take, account_id=account_id)
        items += [_message_item(r) for r in rows]
    if "webhook_delivery" in wanted:
        rows = await repo.failed_deliveries(session, before=before, limit=take)
        items += [_delivery_item(r) for r in rows]
    if "account" in wanted:
        rows = await repo.broken_accounts(session, before=before, limit=take, account_id=account_id)
        items += [_account_item(r) for r in rows]
    items.sort(key=lambda item: (item.occurred_at, item.id), reverse=True)
    more = len(items) > limit
    items = items[:limit]
    return ActivityList(
        items=items,
        next_cursor=encode_cursor(items[-1].occurred_at, items[-1].id) if more and items else None,
    )
