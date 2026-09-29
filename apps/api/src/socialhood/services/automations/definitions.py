"""Automation definitions (T4.3; FR-AUT-01, 02, 12, 13, 15, 19; F-11): create a draft (blank or
from a template), replace the whole definition (the editor's autosave), activate, pause, order,
duplicate and delete. Admins only; nothing here commits.

Rules:
- A draft may be incomplete. Activation checks everything at once (services/automations/
  validation.py) after the plan's entitlements: an AI-reply automation needs ai_reply_automations
  (402 entitlement_required) and the workspace's active automations are capped by
  active_automations (402 quota_exceeded).
- An active automation stays complete: a PUT that would leave it unable to activate is refused
  with the same field errors, and nothing is saved.
- Keywords are stored as typed and normalised (matching.normalize), once per normalised form, in
  the order entered.
- Posts: "selected" stores the chosen media items and scheduled posts; "next_post" keeps the link
  the automation made to its post (services/automations/posts.py) while the account stays the
  same; "all" stores none.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.plans import entitlement
from socialhood.errors import ApiError, FieldError
from socialhood.models.automations import (
    Automation,
    AutomationPost,
    AutomationStatus,
    PostScope,
)
from socialhood.models.connections import SocialAccount
from socialhood.models.media import MediaItem, ResourceType
from socialhood.repositories import automations as repo
from socialhood.repositories import social_accounts
from socialhood.repositories.automations import Keyword, PostRow
from socialhood.schemas.automations import AutomationCreate, AutomationDefinition
from socialhood.services.automations import templates, validation
from socialhood.services.automations.matching import normalize
from socialhood.services.automations.validation import (
    AccountInfo,
    ButtonInfo,
    Definition,
    PostTarget,
)

DEFAULT_NAME = "Untitled automation"
COPY_SUFFIX = " (copy)"
NAME_CHARS = 80
ACTIVE = AutomationStatus.ACTIVE

ACTIVATE_DETAIL = "Finish these steps to activate the automation."
KEEP_COMPLETE_DETAIL = (
    "An active automation has to stay complete. Fix these steps, or pause it to edit freely."
)


# ---------------------------------------------------------------- lookups


async def get_or_404(
    session: AsyncSession, automation_id: uuid.UUID, *, for_update: bool = False
) -> Automation:
    automation = await repo.get(session, automation_id, for_update=for_update)
    if automation is None:
        raise ApiError("not_found")
    return automation


def account_info(acct: SocialAccount | None) -> AccountInfo | None:
    return AccountInfo(platform=acct.platform, status=acct.status) if acct else None


def post_targets(rows: Iterable[PostRow]) -> list[PostTarget]:
    return [
        PostTarget(
            media_item_id=row.link.media_item_id,
            scheduled_post_id=row.link.scheduled_post_id,
            social_account_id=row.item.social_account_id if row.item else None,
        )
        for row in rows
    ]


def definition_of(
    automation: Automation,
    *,
    keywords: Sequence[Keyword],
    posts: Sequence[PostRow],
    account: SocialAccount | None,
) -> Definition:
    """The stored automation as activation sees it."""
    return Definition(
        social_account_id=automation.social_account_id,
        account=account_info(account),
        trigger=automation.trigger,
        keywords=[k.normalized for k in keywords],
        post_scope=automation.post_scope,
        posts=post_targets(posts),
        action=automation.action,
        message_text=automation.message_text,
        message_buttons=[
            ButtonInfo(str(b.get("title", "")), str(b.get("url", "")))
            for b in automation.message_buttons or []
        ],
        public_reply_texts=list(automation.public_reply_texts or []),
        starts_at=automation.starts_at,
        ends_at=automation.ends_at,
    )


async def stored_definition(session: AsyncSession, automation: Automation) -> Definition:
    keywords = (await repo.keywords_for(session, [automation.id]))[automation.id]
    posts = (await repo.posts_for(session, [automation.id]))[automation.id]
    account = (
        await social_accounts.get(session, automation.social_account_id)
        if automation.social_account_id
        else None
    )
    return definition_of(automation, keywords=keywords, posts=posts, account=account)


# ---------------------------------------------------------------- create (FR-AUT-12, F-11)


async def create(
    session: AsyncSession, body: AutomationCreate, *, user_id: uuid.UUID, now: datetime
) -> Automation:
    """A draft, blank or filled from a template. Without an account, the workspace's only live
    Instagram account is used when there is exactly one."""
    errors: list[FieldError] = []
    template = None
    if body.template_key is not None:
        template = templates.find(body.template_key)
        if template is None:
            errors.append(FieldError("template_key", "That template doesn't exist."))
    account_id = body.social_account_id
    if account_id is not None:
        if await social_accounts.get(session, account_id) is None:
            errors.append(FieldError("social_account_id", "That account wasn't found."))
    else:
        live = await repo.live_instagram_accounts(session)
        account_id = live[0].id if len(live) == 1 else None
    if errors:
        raise ApiError("validation_error", errors=errors)

    automation = Automation(
        name=body.name or (template.name if template else DEFAULT_NAME),
        status=AutomationStatus.DRAFT,
        social_account_id=account_id,
        match_mode="word",
        surge_order="oldest_first",
        post_scope=PostScope.ALL,
        cooldown_hours=24,
        public_reply_texts=[],
        message_buttons=[],
        created_by_user_id=user_id,
    )
    if template is not None:
        _fill_from_template(automation, template)
    session.add(automation)
    await session.flush()
    if template is not None and template.keywords:
        await repo.replace_keywords(session, automation.id, _keywords(template.keywords), now)
    await session.flush()
    return automation


def _fill_from_template(automation: Automation, template: templates.Template) -> None:
    automation.template_key = template.key
    automation.trigger = template.trigger
    automation.action = template.action
    automation.message_text = template.message_text
    automation.message_buttons = [
        {"title": b.title, "url": b.url} for b in template.message_buttons
    ]
    automation.ai_instructions = template.ai_instructions
    automation.public_reply_texts = list(template.public_reply_texts)
    automation.post_scope = template.post_scope
    automation.cooldown_hours = template.cooldown_hours


def _keywords(typed: Iterable[str]) -> list[Keyword]:
    found: dict[str, Keyword] = {}
    for keyword in typed:
        normalized = normalize(keyword)
        if normalized and normalized not in found:
            found[normalized] = Keyword(keyword.strip(), normalized)
    return list(found.values())


# ---------------------------------------------------------------- replace the definition (F-11)


@dataclass(frozen=True)
class PostPlan:
    keep: list[uuid.UUID]  # automation_posts ids to keep
    add_media: list[uuid.UUID]
    add_scheduled: list[uuid.UUID]
    targets: list[PostTarget]  # the posts the automation ends up with


def plan_posts(
    automation: Automation,
    body: AutomationDefinition,
    existing: Sequence[PostRow],
    items: dict[uuid.UUID, MediaItem],
) -> PostPlan:
    if body.post_scope == "all":
        return PostPlan([], [], [], [])
    if body.post_scope == "next_post":
        unchanged = (
            automation.post_scope == PostScope.NEXT_POST
            and automation.social_account_id == body.social_account_id
        )
        kept = list(existing) if unchanged else []
        return PostPlan([r.link.id for r in kept], [], [], post_targets(kept))
    media = list(dict.fromkeys(body.media_item_ids))
    scheduled = list(dict.fromkeys(body.scheduled_post_ids))
    kept = [
        r
        for r in existing
        if r.link.scheduled_post_id in scheduled
        or (r.link.media_item_id is not None and r.link.media_item_id in media)
    ]
    kept_media = {r.link.media_item_id for r in kept}
    kept_scheduled = {r.link.scheduled_post_id for r in kept}
    add_media = [m for m in media if m not in kept_media]
    add_scheduled = [s for s in scheduled if s not in kept_scheduled]
    targets = post_targets(kept)
    targets += [PostTarget(m, None, items[m].social_account_id) for m in add_media]
    targets += [PostTarget(None, s, None) for s in add_scheduled]
    return PostPlan([r.link.id for r in kept], add_media, add_scheduled, targets)


def _typed_keywords(keywords: Sequence[str]) -> tuple[list[Keyword], list[FieldError]]:
    errors = [
        FieldError(f"keywords.{i}", "Keep keywords to 100 characters.")
        for i, k in enumerate(keywords)
        if len(k.strip()) > validation.KEYWORD_CHARS
    ]
    return _keywords(keywords), errors


async def _check_references(
    session: AsyncSession, body: AutomationDefinition
) -> tuple[SocialAccount | None, dict[uuid.UUID, MediaItem], list[FieldError]]:
    """The account, posts and image the definition names must be this workspace's."""
    errors: list[FieldError] = []
    account = None
    if body.social_account_id is not None:
        account = await social_accounts.get(session, body.social_account_id)
        if account is None:
            errors.append(FieldError("social_account_id", "That account wasn't found."))
    wanted = list(dict.fromkeys(body.media_item_ids)) if body.post_scope == "selected" else []
    items = {item.id: item for item in await repo.media_items(session, wanted)}
    if len(items) != len(wanted):
        errors.append(FieldError("media_item_ids", "A post wasn't found. Choose it again."))
    if body.message_media_asset_id is not None:
        asset = await repo.get_asset(session, body.message_media_asset_id)
        if asset is None:
            errors.append(
                FieldError("message_media_asset_id", "The image wasn't found. Attach it again.")
            )
        elif asset.resource_type != ResourceType.IMAGE:
            errors.append(FieldError("message_media_asset_id", "Attach an image."))
    return account, items, errors


async def update(
    session: AsyncSession,
    automation_id: uuid.UUID,
    body: AutomationDefinition,
    *,
    disclosure: str | None,
    now: datetime,
) -> Automation:
    """Replace the whole editable definition (autosave)."""
    automation = await get_or_404(session, automation_id, for_update=True)
    account, items, errors = await _check_references(session, body)
    keywords, keyword_errors = _typed_keywords(body.keywords)
    errors += keyword_errors
    if errors:
        raise ApiError("validation_error", errors=errors)

    existing = (await repo.posts_for(session, [automation.id]))[automation.id]
    posts = plan_posts(automation, body, existing, items)
    if automation.status == ACTIVE:
        problems = validation.activation_errors(
            _definition_from_body(body, account, keywords, posts.targets),
            disclosure=disclosure,
            now=now,
        )
        if problems:
            raise ApiError("validation_error", KEEP_COMPLETE_DETAIL, errors=problems)

    _apply(automation, body)
    await repo.replace_keywords(session, automation.id, keywords, now)
    await repo.delete_posts(session, automation.id, keep=posts.keep)
    session.add_all(
        [AutomationPost(automation_id=automation.id, media_item_id=m) for m in posts.add_media]
        + [
            AutomationPost(automation_id=automation.id, scheduled_post_id=s)
            for s in posts.add_scheduled
        ]
    )
    await session.flush()
    return automation


def _definition_from_body(
    body: AutomationDefinition,
    account: SocialAccount | None,
    keywords: Sequence[Keyword],
    posts: Sequence[PostTarget],
) -> Definition:
    return Definition(
        social_account_id=body.social_account_id,
        account=account_info(account),
        trigger=body.trigger,
        keywords=[k.normalized for k in keywords],
        post_scope=body.post_scope,
        posts=posts,
        action=body.action,
        message_text=body.message_text,
        message_buttons=[ButtonInfo(b.title, b.url) for b in body.message_buttons],
        public_reply_texts=body.public_reply_texts,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
    )


def _apply(automation: Automation, body: AutomationDefinition) -> None:
    automation.name = body.name
    automation.social_account_id = body.social_account_id
    automation.trigger = body.trigger
    automation.match_mode = body.match_mode
    automation.action = body.action
    automation.message_text = body.message_text or None
    automation.message_buttons = [{"title": b.title, "url": b.url} for b in body.message_buttons]
    automation.message_media_asset_id = body.message_media_asset_id
    automation.ai_instructions = body.ai_instructions or None
    automation.public_reply_texts = list(body.public_reply_texts)
    automation.post_scope = body.post_scope
    automation.cooldown_hours = body.cooldown_hours
    automation.starts_at = body.starts_at
    automation.ends_at = body.ends_at
    automation.surge_order = body.surge_order


# ---------------------------------------------------------------- activate and pause


async def activate(
    session: AsyncSession,
    automation_id: uuid.UUID,
    *,
    plan: str,
    disclosure: str | None,
    now: datetime,
) -> Automation:
    """FR-AUT-02: entitlements, then every missing or invalid field in one 422, then the plan's
    active-automation limit. Activating an active automation changes nothing."""
    automation = await get_or_404(session, automation_id, for_update=True)
    if automation.status == ACTIVE:
        return automation
    if automation.action == "ai_reply" and not entitlement(plan, "ai_reply_automations"):
        raise ApiError("entitlement_required", "AI replies in automations are part of Pro.")
    definition = await stored_definition(session, automation)
    errors = validation.activation_errors(definition, disclosure=disclosure, now=now)
    if errors:
        raise ApiError("validation_error", ACTIVATE_DETAIL, errors=errors)
    limit = entitlement(plan, "active_automations")
    if limit is not None and await repo.count_active(session, excluding=automation.id) >= limit:
        raise ApiError("quota_exceeded", f"Your plan includes {limit} active automations.")
    automation.status = ACTIVE
    automation.activated_at = now
    automation.paused_at = None
    await session.flush()
    return automation


def _pause(automation: Automation, now: datetime) -> bool:
    if automation.status != ACTIVE:
        return False
    automation.status = AutomationStatus.PAUSED
    automation.paused_at = now
    return True


async def pause(session: AsyncSession, automation_id: uuid.UUID, *, now: datetime) -> Automation:
    """Pausing a draft or a paused automation changes nothing."""
    automation = await get_or_404(session, automation_id, for_update=True)
    if _pause(automation, now):
        await session.flush()
    return automation


async def pause_many(session: AsyncSession, ids: Sequence[uuid.UUID], *, now: datetime) -> int:
    """FR-AUT-19: pause several at once; every id must be this workspace's. Returns how many
    were active."""
    wanted = list(dict.fromkeys(ids))
    automations = await repo.get_many(session, wanted, for_update=True)
    if len(automations) != len(wanted):
        raise ApiError("not_found")
    paused = sum(_pause(a, now) for a in automations)
    await session.flush()
    return paused


# ---------------------------------------------------------------- order (FR-AUT-15)


async def reorder(
    session: AsyncSession, social_account_id: uuid.UUID, ordered_ids: Sequence[uuid.UUID]
) -> None:
    """The account's automations take priorities 1, 2, 3… in the given order; the ones not
    listed follow in their current order."""
    if await social_accounts.get(session, social_account_id) is None:
        raise ApiError("not_found")
    wanted = list(dict.fromkeys(ordered_ids))
    named = await repo.get_many(session, wanted)
    if len(named) != len(wanted):
        raise ApiError("not_found")
    if any(a.social_account_id != social_account_id for a in named):
        raise ApiError(
            "validation_error",
            errors=[FieldError("ordered_ids", "Only this account's automations can be ordered.")],
        )
    current = await repo.for_account(session, social_account_id, for_update=True)
    by_id = {a.id: a for a in current}
    order = [by_id[i] for i in wanted] + [a for a in current if a.id not in set(wanted)]
    for position, automation in enumerate(order, start=1):
        if automation.priority != position:
            automation.priority = position
    await session.flush()


# ---------------------------------------------------------------- duplicate and delete


def copy_name(name: str) -> str:
    return name[: NAME_CHARS - len(COPY_SUFFIX)].rstrip() + COPY_SUFFIX


async def duplicate(
    session: AsyncSession, automation_id: uuid.UUID, *, user_id: uuid.UUID, now: datetime
) -> Automation:
    """A draft copy with the same definition, keywords and selected posts (FR-AUT-19)."""
    source = await get_or_404(session, automation_id)
    copy = Automation(
        name=copy_name(source.name),
        status=AutomationStatus.DRAFT,
        social_account_id=source.social_account_id,
        trigger=source.trigger,
        match_mode=source.match_mode,
        action=source.action,
        message_text=source.message_text,
        ai_instructions=source.ai_instructions,
        public_reply_texts=list(source.public_reply_texts or []),
        message_buttons=[dict(b) for b in source.message_buttons or []],
        message_media_asset_id=source.message_media_asset_id,
        template_key=source.template_key,
        starts_at=source.starts_at,
        ends_at=source.ends_at,
        surge_order=source.surge_order,
        post_scope=source.post_scope,
        cooldown_hours=source.cooldown_hours,
        created_by_user_id=user_id,
    )
    session.add(copy)
    await session.flush()
    keywords = (await repo.keywords_for(session, [source.id]))[source.id]
    await repo.replace_keywords(session, copy.id, keywords, now)
    if source.post_scope == PostScope.SELECTED:
        rows = (await repo.posts_for(session, [source.id]))[source.id]
        session.add_all(
            AutomationPost(
                automation_id=copy.id,
                media_item_id=r.link.media_item_id,
                scheduled_post_id=r.link.scheduled_post_id,
            )
            for r in rows
        )
    await session.flush()
    return copy


async def delete(session: AsyncSession, automation_id: uuid.UUID) -> None:
    await get_or_404(session, automation_id)
    await repo.delete(session, automation_id)
