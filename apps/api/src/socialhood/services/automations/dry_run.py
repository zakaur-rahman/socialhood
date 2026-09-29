"""The editor's Test tab (T4.3, T4.8; UX-SCR-03, FR-AUT-21, FR-AUT-22): what would happen for a
DM or comment. Sends nothing and writes nothing.

It says whether this automation matches the text (and, for a comment on a chosen post, whether
the post is in its scope), which automation of the account would actually answer, why this one
would not, and the message and public reply it would send, rendered with a sample name (or the
name given; an empty name shows the fallback). For a comment with tap first it adds the opening;
with the follow nudge, the nudge a non-follower would get after the message (none for a comment
automation without tap first, which never hears back from the person). Messages, the opening and
the nudge carry the disclosure line.

The automation under test is treated as live, so a draft can be tried before it is activated; the
other candidates are the account's active automations inside their run window, as the runtime
loads them. Cooldowns are not applied (there is no contact).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError, FieldError
from socialhood.models.automations import Automation, AutomationStatus
from socialhood.models.media import MediaItem
from socialhood.repositories import automations as repo
from socialhood.repositories.automations import PostRow
from socialhood.schemas.automations import AutomationTest, AutomationTestResult, WinningAutomation
from socialhood.services.automations import actions, matching, render, windows
from socialhood.services.automations.queries import candidate
from socialhood.services.automations.validation import COMMENT_TRIGGERS

SAMPLE_FIRST_NAME = "Priya"
SAMPLE_USERNAME = "priya.shah"
TRIGGERS_FOR = {"dm": ("dm_keyword",), "comment": ("comment_keyword", "comment_any")}


def _sample(body: AutomationTest) -> tuple[str | None, str | None]:
    if body.first_name is None and body.username is None:
        return SAMPLE_FIRST_NAME, SAMPLE_USERNAME
    return body.first_name or None, body.username or None


@dataclass(frozen=True)
class _Rendered:
    message: str | None = None
    public: str | None = None
    opening: str | None = None
    nudge: str | None = None


def _rendered(automation: Automation, body: AutomationTest, disclosure: str | None) -> _Rendered:
    first_name, username = _sample(body)

    def message_like(text: str) -> str:
        return render.with_disclosure(
            render.render(text, first_name=first_name, username=username), disclosure
        )

    message = None
    if automation.action == "send_message" and automation.message_text:
        message = message_like(automation.message_text)
    public = opening = None
    if body.kind == "comment" and automation.trigger in COMMENT_TRIGGERS:
        texts = [t for t in automation.public_reply_texts or [] if t.strip()]
        if texts:
            public = render.render(texts[0], first_name=first_name, username=username)
        if actions.opens_first(automation):
            opening = message_like(automation.opening_text or "")
    nudge = None
    # The nudge needs an answer from the person: a DM, or a tap-first comment's tap or reply.
    answered = automation.trigger not in COMMENT_TRIGGERS or actions.opens_first(automation)
    if answered and actions.render_nudge(automation, None, disclosure_line=None) is not None:
        nudge = message_like(automation.follow_nudge_text or "")
    return _Rendered(message, public, opening, nudge)


def _in_scope(automation: Automation, posts: Sequence[PostRow], item: MediaItem | None) -> bool:
    """Without a post, the scope is not checked; with one, "all" takes any post of the account
    and the other scopes only their linked posts."""
    if item is None:
        return True
    if automation.post_scope == "all":
        return True
    return any(r.link.media_item_id == item.id for r in posts)


async def run(
    session: AsyncSession,
    automation: Automation,
    body: AutomationTest,
    *,
    disclosure: str | None,
    now: datetime,
) -> AutomationTestResult:
    item = None
    if body.media_item_id is not None:
        item = await repo.get_media_item(session, body.media_item_id)
        if item is None:
            raise ApiError(
                "validation_error",
                errors=[FieldError("media_item_id", "That post wasn't found.")],
            )
    rendered = _rendered(automation, body, disclosure)

    def result(
        reason: str | None,
        *,
        matched: bool = False,
        keyword: str | None = None,
        winner: Automation | None = None,
    ) -> AutomationTestResult:
        return AutomationTestResult(
            matched=matched,
            matched_keyword=keyword,
            winner=WinningAutomation(id=winner.id, name=winner.name) if winner else None,
            reason=reason,
            rendered_message=rendered.message,
            rendered_public_reply=rendered.public,
            rendered_opening=rendered.opening,
            rendered_nudge=rendered.nudge,
        )

    account_id, trigger = automation.social_account_id, automation.trigger
    kinds = TRIGGERS_FOR[body.kind]
    if account_id is None or trigger is None:
        return result("Choose an account and a trigger first.")
    if trigger not in kinds:
        other = "comments" if body.kind == "dm" else "DMs"
        return result(f"This automation answers {other}, not {_plural(body.kind)}.")
    if item is not None and item.social_account_id != account_id:
        return result("That post belongs to another account.")

    others = [
        x
        for x in await repo.for_account(session, account_id)
        if x.id != automation.id
        and x.status == AutomationStatus.ACTIVE
        and x.trigger in kinds
        and windows.in_window(x, now)
    ]
    everyone = {x.id: x for x in [automation, *others]}
    keywords = await repo.keywords_for(session, list(everyone))
    posts = await repo.posts_for(session, list(everyone))
    text = matching.normalize(body.text)

    def fires(c: matching.Candidate) -> bool:
        return matching.matching_keyword(text, c) is not None and _in_scope(
            everyone[c.id], posts[c.id], item
        )

    ordered = matching.runtime_order(candidate(x, keywords[x.id]) for x in everyone.values())
    first = next((c for c in ordered if fires(c)), None)
    winner = everyone[first.id] if first else None

    this = candidate(automation, keywords[automation.id])
    found = matching.matching_keyword(text, this)
    typed = {k.normalized: k.keyword for k in keywords[automation.id]}
    keyword = typed.get(found, found) if found else None
    if found is None:
        return result(f"None of its keywords is in this {_noun(body.kind)}.", winner=winner)
    if not _in_scope(automation, posts[automation.id], item):
        return result("This post isn't one of the automation's posts.", winner=winner)
    if winner is not None and winner.id != automation.id:
        why = (
            "keyword automations run before any-comment ones"
            if winner.trigger != "comment_any" and trigger == "comment_any"
            else "it's higher in the list"
        )
        return result(
            f"“{winner.name}” runs first: {why}.", matched=True, keyword=keyword, winner=winner
        )
    return result(_live_reason(automation, now), matched=True, keyword=keyword, winner=winner)


def _live_reason(automation: Automation, now: datetime) -> str | None:
    if automation.status != AutomationStatus.ACTIVE:
        return "It matches. It will run once you activate it."
    if automation.starts_at is not None and now < automation.starts_at:
        return "It matches, and it will run once its run window starts."
    if automation.ends_at is not None and now >= automation.ends_at:
        return "It matches, but its run window has ended."
    return None


def _noun(kind: str) -> str:
    return "message" if kind == "dm" else "comment"


def _plural(kind: str) -> str:
    return "DMs" if kind == "dm" else "comments"
