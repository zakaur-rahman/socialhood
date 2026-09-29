"""What activation needs (FR-AUT-02, FR-AUT-13, FR-AUT-14, FR-AUT-17; TR-PL-10). Pure: no
database, no clock.

``activation_errors`` returns every missing or invalid field at once, so the editor can mark each
step: an account (a connected Instagram account), a trigger, keywords (except any-comment, which
needs selected posts or the next post instead), an action, the message text for "send a message",
https link buttons with titles of at most 20 characters, a message of at most 1,000 bytes on
Instagram in its longest rendering with the workspace's disclosure line, public replies of at most
300 characters, and a run window that ends after it starts and has not ended yet.

AI replies need the knowledge base and suggestions (P5), so an AI-reply automation cannot be
activated yet; the error says so on the action field.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

from socialhood.errors import FieldError
from socialhood.services.automations import render

INSTAGRAM_MESSAGE_BYTES = 1000  # TR-PL-10
PUBLIC_REPLY_CHARS = 300  # FR-AUT-14
BUTTON_TITLE_CHARS = 20  # FR-AUT-13
KEYWORD_CHARS = 100  # automation_keywords.keyword
COMMENT_TRIGGERS = frozenset({"comment_keyword", "comment_any"})
KEYWORD_TRIGGERS = frozenset({"dm_keyword", "comment_keyword"})

COPY = {
    "account_missing": "Choose the account this automation runs on.",
    "account_platform": "Automations run on Instagram accounts. Choose an Instagram account.",
    "account_disconnected": "This account is disconnected. Reconnect it or choose another.",
    "trigger_missing": "Choose what starts the automation.",
    "keywords_missing": "Add at least one keyword.",
    "scope_all_any_comment": "Choose the posts to answer, or the next post you publish.",
    "posts_missing": "Choose at least one post.",
    "posts_other_account": "Choose posts from this automation's account.",
    "action_missing": "Choose what the automation does.",
    "ai_reply_later": "AI replies arrive with the knowledge base. Send a message for now.",
    "message_missing": "Write the message to send.",
    "button_url": "Use a full link that starts with https://.",
    "button_title": "Give the button a title of up to 20 characters.",
    "reply_empty": "Write this reply or remove it.",
    "reply_long": "Keep public replies to 300 characters.",
    "window_order": "The end must be after the start.",
    "window_past": "This end time has passed. Pick a later one or remove it.",
}


@dataclass(frozen=True)
class AccountInfo:
    platform: str
    status: str


@dataclass(frozen=True)
class PostTarget:
    media_item_id: uuid.UUID | None
    scheduled_post_id: uuid.UUID | None
    social_account_id: uuid.UUID | None  # the post's account; None until a scheduled post publishes


@dataclass(frozen=True)
class ButtonInfo:
    title: str
    url: str


@dataclass(frozen=True)
class Definition:
    """An automation as activation sees it: stored, or as a PUT would leave it."""

    social_account_id: uuid.UUID | None
    account: AccountInfo | None  # None when there is no account or it was not found
    trigger: str | None
    keywords: Sequence[str]
    post_scope: str
    posts: Sequence[PostTarget]
    action: str | None
    message_text: str | None
    message_buttons: Sequence[ButtonInfo]
    public_reply_texts: Sequence[str]
    starts_at: datetime | None
    ends_at: datetime | None


def is_https_url(url: str) -> bool:
    """An absolute https address with a host name (FR-AUT-13)."""
    if not url or any(c.isspace() for c in url):
        return False
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:
        return False
    return parts.scheme == "https" and bool(host) and "." in (host or "").strip(".")


def message_bytes(text: str, disclosure: str | None) -> int:
    """The message's size in its longest rendering, with the disclosure line (TR-PL-10)."""
    return render.utf8_bytes(render.with_disclosure(render.longest_render(text), disclosure))


def activation_errors(d: Definition, *, disclosure: str | None, now: datetime) -> list[FieldError]:
    errors: list[FieldError] = []
    errors += _account_errors(d)
    errors += _trigger_errors(d)
    errors += _action_errors(d, disclosure)
    errors += _window_errors(d, now)
    return errors


def missing_fields(errors: Sequence[FieldError]) -> list[str]:
    """The fields named by ``errors``, once each, in order."""
    return list(dict.fromkeys(e.field for e in errors))


def _account_errors(d: Definition) -> list[FieldError]:
    if d.social_account_id is None or d.account is None:
        return [FieldError("social_account_id", COPY["account_missing"])]
    if d.account.platform != "instagram":
        return [FieldError("social_account_id", COPY["account_platform"])]
    if d.account.status == "disconnected":
        return [FieldError("social_account_id", COPY["account_disconnected"])]
    return []


def _trigger_errors(d: Definition) -> list[FieldError]:
    if d.trigger is None:
        return [FieldError("trigger", COPY["trigger_missing"])]
    errors: list[FieldError] = []
    if d.trigger in KEYWORD_TRIGGERS and not d.keywords:
        errors.append(FieldError("keywords", COPY["keywords_missing"]))
    if d.trigger in COMMENT_TRIGGERS:
        errors += _post_errors(d)
    return errors


def _post_errors(d: Definition) -> list[FieldError]:
    if d.post_scope == "all":
        if d.trigger == "comment_any":
            return [FieldError("post_scope", COPY["scope_all_any_comment"])]
        return []
    if d.post_scope != "selected":
        return []  # next_post: linked when the post appears (FR-AUT-18)
    if not d.posts:
        return [FieldError("media_item_ids", COPY["posts_missing"])]
    if d.social_account_id is not None and any(
        p.social_account_id not in (None, d.social_account_id) for p in d.posts
    ):
        return [FieldError("media_item_ids", COPY["posts_other_account"])]
    return []


def _action_errors(d: Definition, disclosure: str | None) -> list[FieldError]:
    if d.action is None:
        return [FieldError("action", COPY["action_missing"])]
    errors: list[FieldError] = []
    if d.action == "ai_reply":
        errors.append(FieldError("action", COPY["ai_reply_later"]))
    elif d.action == "send_message":
        errors += _message_errors(d, disclosure)
    if d.trigger in COMMENT_TRIGGERS:
        errors += _public_reply_errors(d.public_reply_texts)
    return errors


def _message_errors(d: Definition, disclosure: str | None) -> list[FieldError]:
    errors: list[FieldError] = []
    text = (d.message_text or "").strip()
    if not text:
        errors.append(FieldError("message_text", COPY["message_missing"]))
    else:
        size = message_bytes(text, disclosure)
        if size > INSTAGRAM_MESSAGE_BYTES:
            errors.append(
                FieldError(
                    "message_text",
                    f"Instagram allows {INSTAGRAM_MESSAGE_BYTES:,} bytes. With a long name"
                    f"{' and the disclosure line' if disclosure else ''} this message is "
                    f"{size:,}. Shorten it.",
                )
            )
    for i, button in enumerate(d.message_buttons):
        if not 1 <= len(button.title.strip()) <= BUTTON_TITLE_CHARS:
            errors.append(FieldError(f"message_buttons.{i}.title", COPY["button_title"]))
        if not is_https_url(button.url.strip()):
            errors.append(FieldError(f"message_buttons.{i}.url", COPY["button_url"]))
    return errors


def _public_reply_errors(texts: Sequence[str]) -> list[FieldError]:
    errors: list[FieldError] = []
    for i, text in enumerate(texts):
        if not text.strip():
            errors.append(FieldError(f"public_reply_texts.{i}", COPY["reply_empty"]))
        elif len(text) > PUBLIC_REPLY_CHARS:
            errors.append(FieldError(f"public_reply_texts.{i}", COPY["reply_long"]))
    return errors


def _window_errors(d: Definition, now: datetime) -> list[FieldError]:
    if d.ends_at is None:
        return []
    if d.starts_at is not None and d.ends_at <= d.starts_at:
        return [FieldError("ends_at", COPY["window_order"])]
    if d.ends_at <= now:
        return [FieldError("ends_at", COPY["window_past"])]
    return []
