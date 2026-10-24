"""What activation needs (FR-AUT-02, FR-AUT-13, FR-AUT-14, FR-AUT-17, FR-AUT-21, FR-AUT-22;
TR-PL-10). Pure: no database, no clock.

``activation_errors`` returns every missing or invalid field at once, so the editor can mark each
step: an account (a connected Instagram account), a trigger, keywords (except any-comment, which
needs selected posts or the next post instead), an action, the message text for "send a message",
https link buttons with titles of at most 20 characters, a message of at most 1,000 bytes on
Instagram in its longest rendering with the workspace's disclosure line, public replies of at most
300 characters, and a run window that ends after it starts and has not ended yet. With link
buttons the text is Instagram's button template, at most 640 characters in its longest rendering.
A comment automation's DM is a private reply, which Instagram sends as text (and buttons) only,
so it cannot carry an image; one set to public reply only needs a public reply.

Facebook Pages (GR-29) run the same automations on Messenger where Meta allows it. A message is
at most 2,000 characters in its longest rendering (the Send API's text limit); link buttons, tap
first, public replies and private replies work as on Instagram. Not on Messenger, so activation
refuses them in plain words: story replies and story mentions (Pages have none), Live comments,
and the follow nudge (Messenger doesn't say whether someone follows the Page).

Story triggers (GR-06, GR-07) are DM triggers. A story reply takes keywords or none (any reply), and
its scope is any story or at least one chosen story; a story mention needs nothing but a message.

Entry triggers (GR-08, GR-09) are DM triggers that need no keywords: an entry link automation
needs nothing but a message (its links are made on the Entry links page); an ad click automation
answers any ad or at least one chosen ad id.

Tap first (FR-AUT-21, comment triggers sending a message): the private reply is the opening, so
it needs its text (1,000 bytes at most in its longest rendering with the disclosure line) and a
button title of 1 to 20 characters; the message follows their answer as a normal DM, so it may
carry an image. On a DM trigger the setting is ignored. The follow nudge (FR-AUT-22) needs its
text, at most 300 characters as typed. AI replies ignore both settings.

An AI reply (T5.8, FR-AUT-01) needs its instructions: what the business wants the reply to do
(at most 2,000 characters, enforced by the request schema). Its plan entitlement is checked
before these rules (definitions.activate).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

from socialhood.errors import FieldError
from socialhood.services.automations import render, templates

INSTAGRAM_MESSAGE_BYTES = 1000  # TR-PL-10
FACEBOOK_MESSAGE_CHARS = 2000  # Messenger's text limit (unverified, GR-29)
AUTOMATION_PLATFORMS = ("instagram", "facebook")
PUBLIC_REPLY_CHARS = 300  # FR-AUT-14
BUTTON_TITLE_CHARS = 20  # FR-AUT-13
BUTTON_TEXT_CHARS = 640  # the button template's text (services/sending.BUTTON_TEXT_LIMITS)
KEYWORD_CHARS = 100  # automation_keywords.keyword
NUDGE_CHARS = 300  # FR-AUT-22, automations.follow_nudge_text
COMMENT_TRIGGERS = frozenset({"comment_keyword", "comment_any"})
KEYWORD_TRIGGERS = frozenset({"dm_keyword", "comment_keyword"})  # story_reply's are optional

COPY = {
    "account_missing": "Choose the account this automation runs on.",
    "account_platform": (
        "Automations run on Instagram and Facebook accounts. Choose one of those."
    ),
    "facebook_stories": (
        "Facebook Pages have no story replies or story mentions. Choose another trigger."
    ),
    "facebook_live": (
        "Live comments on Facebook aren't supported yet. Answer comments on posts instead."
    ),
    "facebook_follow": (
        "Messenger doesn't say whether someone follows your Page, so the follow line can't be "
        "used. Turn it off."
    ),
    "account_disconnected": "This account is disconnected. Reconnect it or choose another.",
    "trigger_missing": "Choose what starts the automation.",
    "keywords_missing": "Add at least one keyword.",
    "scope_all_any_comment": "Choose the posts to answer, or the next post you publish.",
    "posts_missing": "Choose at least one post.",
    "stories_missing": "Choose at least one story, or answer any story.",
    "story_scope": "A story reply answers any story or the stories you choose.",
    "ads_missing": "Add at least one ad id, or answer any ad.",
    "ad_scope": "An ad click answers any ad or the ads you choose.",
    "posts_other_account": "Choose posts from this automation's account.",
    "action_missing": "Choose what the automation does.",
    "ai_instructions_missing": "Tell the AI how to reply, for example what to offer or link to.",
    "message_missing": "Write the message to send.",
    "button_url": "Use a full link that starts with https://.",
    "button_title": "Give the button a title of up to 20 characters.",
    "button_text_long": "With link buttons Instagram allows 640 characters. Shorten the message.",
    "image_in_private_reply": (
        "Instagram's replies to comments can't include an image. Remove it, or link to it with "
        "a button."
    ),
    "public_only_needs_reply": "Add a public reply. This automation only replies publicly.",
    "opening_missing": "Write the opening message people get first.",
    "opening_button": "Give the button a title of up to 20 characters.",
    "nudge_missing": "Write the follow line, or turn the follow nudge off.",
    "nudge_long": "Keep the follow line to 300 characters.",
    "reply_empty": "Write this reply or remove it.",
    "reply_long": "Keep public replies to 300 characters.",
    "window_order": "The end must be after the start.",
    "window_past": "This end time has passed. Pick a later one or remove it.",
}


def localize(text: str, platform: str | None) -> str:
    """Copy written for Instagram, said for the account's platform."""
    return text.replace("Instagram", "Facebook") if platform == "facebook" else text


def message_limit(platform: str | None) -> tuple[int, str]:
    """(the most a message may be, its unit) on the platform (TR-PL-10)."""
    if platform == "facebook":
        return FACEBOOK_MESSAGE_CHARS, "characters"
    return INSTAGRAM_MESSAGE_BYTES, "bytes"


def message_size(platform: str | None, text: str, disclosure: str | None) -> int:
    """The message in its longest rendering with the disclosure line, in the platform's unit."""
    if platform == "facebook":
        return len(render.with_disclosure(render.longest_render(text), disclosure))
    return message_bytes(text, disclosure)


def too_long_copy(
    platform: str | None, size: int, *, what: str, disclosure: str | None
) -> str | None:
    """The validation message when ``size`` is over the platform's limit, else None."""
    limit, unit = message_limit(platform)
    if size <= limit:
        return None
    name = "Facebook" if platform == "facebook" else "Instagram"
    return (
        f"{name} allows {limit:,} {unit}. With a long name"
        f"{' and the disclosure line' if disclosure else ''} this {what} is "
        f"{size:,}. Shorten it."
    )


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
    surge_order: str = "oldest_first"
    story_ids: Sequence[str] = ()  # GR-06: a story reply's chosen stories
    ad_ids: Sequence[str] = ()  # GR-09: an ad click's chosen ads
    comment_surface: str = "posts"  # GR-10: posts, live or both (comment triggers)
    has_image: bool = False
    confirm_first: bool = False
    opening_text: str | None = None
    opening_button: str | None = None
    follow_nudge: bool = False
    follow_nudge_text: str | None = None
    ai_instructions: str | None = None
    # GR-03: saved as a flow, whose own checks (services/automations/flows) replace the message,
    # opening, nudge and AI checks here.
    uses_flow: bool = False

    @property
    def platform(self) -> str | None:
        return self.account.platform if self.account else None

    @property
    def taps_first(self) -> bool:
        """Tap first applies: a comment trigger sending a message (FR-AUT-21)."""
        return (
            self.confirm_first
            and self.trigger in COMMENT_TRIGGERS
            and self.action == "send_message"
        )

    @property
    def nudges(self) -> bool:
        """The follow nudge applies: an automation sending a message (FR-AUT-22); AI replies
        ignore it."""
        return self.follow_nudge and self.action == "send_message"


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


def placeholder_errors(field: str, text: str | None) -> list[FieldError]:
    """One error for each template placeholder ("[price]") still in the text."""
    return [FieldError(field, templates.unfilled_copy(t)) for t in templates.unfilled(text or "")]


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
    if d.account.platform not in AUTOMATION_PLATFORMS:
        return [FieldError("social_account_id", COPY["account_platform"])]
    if d.account.status == "disconnected":
        return [FieldError("social_account_id", COPY["account_disconnected"])]
    return []


def _trigger_errors(d: Definition) -> list[FieldError]:
    if d.trigger is None:
        return [FieldError("trigger", COPY["trigger_missing"])]
    if d.platform == "facebook":
        if d.trigger in ("story_reply", "story_mention"):
            return [FieldError("trigger", COPY["facebook_stories"])]
        if d.trigger in COMMENT_TRIGGERS and d.comment_surface != "posts":
            return [FieldError("comment_surface", COPY["facebook_live"])]
    errors: list[FieldError] = []
    if d.trigger in KEYWORD_TRIGGERS and not d.keywords:
        errors.append(FieldError("keywords", COPY["keywords_missing"]))
    if d.trigger in COMMENT_TRIGGERS and d.comment_surface != "live":
        errors += _post_errors(d)  # a Live-only automation has no post scope (GR-10)
    if d.trigger == "story_reply":
        errors += _story_errors(d)
    if d.trigger == "ad_click":
        errors += _ad_errors(d)
    return errors


def _ad_errors(d: Definition) -> list[FieldError]:
    if d.post_scope == "next_post":
        return [FieldError("post_scope", COPY["ad_scope"])]
    if d.post_scope == "selected" and not d.ad_ids:
        return [FieldError("ad_ids", COPY["ads_missing"])]
    return []


def _story_errors(d: Definition) -> list[FieldError]:
    if d.post_scope == "next_post":
        return [FieldError("post_scope", COPY["story_scope"])]
    if d.post_scope == "selected" and not d.story_ids:
        return [FieldError("story_ids", COPY["stories_missing"])]
    return []


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
    if d.action is None and not d.uses_flow:
        return [FieldError("action", COPY["action_missing"])]
    errors: list[FieldError] = []
    if not d.uses_flow:
        errors += _message_settings_errors(d, disclosure)
    if d.trigger in COMMENT_TRIGGERS:
        errors += _public_reply_errors(d.public_reply_texts)
        if d.surge_order == "public_only" and not d.public_reply_texts:
            errors.append(FieldError("public_reply_texts", COPY["public_only_needs_reply"]))
    return errors


def _message_settings_errors(d: Definition, disclosure: str | None) -> list[FieldError]:
    errors: list[FieldError] = []
    if d.action == "ai_reply":
        if not (d.ai_instructions or "").strip():
            errors.append(FieldError("ai_instructions", COPY["ai_instructions_missing"]))
    elif d.action == "send_message":
        errors += _message_errors(d, disclosure)
    if d.taps_first:
        errors += _opening_errors(d, disclosure)
    if d.nudges and d.platform == "facebook":
        errors.append(FieldError("follow_nudge", COPY["facebook_follow"]))
    elif d.nudges:
        errors += _nudge_errors(d)
    return errors


def _message_errors(d: Definition, disclosure: str | None) -> list[FieldError]:
    errors: list[FieldError] = []
    text = (d.message_text or "").strip()
    if not text:
        errors.append(FieldError("message_text", COPY["message_missing"]))
    else:
        errors += placeholder_errors("message_text", text)
        size = message_size(d.platform, text, disclosure)
        problem = too_long_copy(d.platform, size, what="message", disclosure=disclosure)
        if problem:
            errors.append(FieldError("message_text", problem))
        longest = render.with_disclosure(render.longest_render(text), disclosure)
        if d.message_buttons and len(longest) > BUTTON_TEXT_CHARS:
            errors.append(
                FieldError("message_text", localize(COPY["button_text_long"], d.platform))
            )
    if d.has_image and d.trigger in COMMENT_TRIGGERS and not d.taps_first:
        errors.append(
            FieldError(
                "message_media_asset_id", localize(COPY["image_in_private_reply"], d.platform)
            )
        )
    for i, button in enumerate(d.message_buttons):
        if not 1 <= len(button.title.strip()) <= BUTTON_TITLE_CHARS:
            errors.append(FieldError(f"message_buttons.{i}.title", COPY["button_title"]))
        if not is_https_url(button.url.strip()):
            errors.append(FieldError(f"message_buttons.{i}.url", COPY["button_url"]))
    return errors


def _opening_errors(d: Definition, disclosure: str | None) -> list[FieldError]:
    errors: list[FieldError] = []
    text = (d.opening_text or "").strip()
    if not text:
        errors.append(FieldError("opening_text", COPY["opening_missing"]))
    else:
        errors += placeholder_errors("opening_text", text)
        size = message_size(d.platform, text, disclosure)
        problem = too_long_copy(d.platform, size, what="opening", disclosure=disclosure)
        if problem:
            errors.append(FieldError("opening_text", problem))
    if not 1 <= len((d.opening_button or "").strip()) <= BUTTON_TITLE_CHARS:
        errors.append(FieldError("opening_button", COPY["opening_button"]))
    return errors


def _nudge_errors(d: Definition) -> list[FieldError]:
    """The follow line as typed: required, at most 300 characters (personal fields and the
    disclosure line are added when it is sent)."""
    if not (d.follow_nudge_text or "").strip():
        return [FieldError("follow_nudge_text", COPY["nudge_missing"])]
    errors = placeholder_errors("follow_nudge_text", d.follow_nudge_text)
    if len(d.follow_nudge_text or "") > NUDGE_CHARS:
        errors.append(FieldError("follow_nudge_text", COPY["nudge_long"]))
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
