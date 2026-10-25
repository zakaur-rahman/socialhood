"""The caption limit per platform (C-131): 2,200 characters for Instagram, 63,206 for a Facebook
Page, the strictest of a cross-posted post's accounts."""

from __future__ import annotations

from datetime import UTC, datetime

from socialhood.models.publishing import (
    CAPTION_MAX_CHARS,
    FACEBOOK_CAPTION_MAX_CHARS,
    STORED_CAPTION_MAX_CHARS,
)
from socialhood.schemas.publishing import ScheduledPostDraft, TargetIn
from socialhood.services.scheduled_posts import rules
from socialhood.services.scheduled_posts.rules import AssetFacts, PostFacts, TargetFacts

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)


def _target(platform: str, override: str | None = None, handle: str = "@shop") -> TargetFacts:
    return TargetFacts(
        handle=handle,
        status="active",
        can_publish=True,
        caption_override=override,
        recent_posts=0,
        platform=platform,
    )


def _image() -> AssetFacts:
    return AssetFacts("image", "jpg", 200_000, 1080, 1350, None)


def _post(targets: list[TargetFacts], caption: str) -> PostFacts:
    return PostFacts(
        targets=targets, assets=[_image()], caption=caption, first_comment=None, publish_at=None
    )


def _failing(post: PostFacts) -> list[tuple[str, str | None]]:
    items = rules.checklist(post, now=NOW, publishing_limit=100)
    return [(i.key, i.field) for i in items if not i.ok]


def test_the_limits() -> None:
    assert (CAPTION_MAX_CHARS, FACEBOOK_CAPTION_MAX_CHARS) == (2200, 63_206)
    assert STORED_CAPTION_MAX_CHARS == FACEBOOK_CAPTION_MAX_CHARS
    assert rules.caption_limit([]) == 2200
    assert rules.caption_limit(["instagram"]) == 2200
    assert rules.caption_limit(["facebook"]) == 63_206
    assert rules.caption_limit(["facebook", "facebook"]) == 63_206
    assert rules.caption_limit(["facebook", "instagram"]) == 2200


def test_a_page_post_may_be_long_but_an_instagram_post_may_not() -> None:
    long = "x" * 5000
    assert _failing(_post([_target("facebook")], long)) == []
    assert _failing(_post([_target("instagram")], long)) == [("caption", "caption")]
    assert _failing(_post([_target("facebook")], "x" * 63_207)) == [("caption", "caption")]


def test_a_cross_post_is_held_to_the_strictest_account() -> None:
    both = [_target("facebook", handle="@page"), _target("instagram", handle="@shop")]
    assert _failing(_post(both, "x" * 3000)) == [("caption", "caption")]
    assert _failing(_post(both, "x" * 2200)) == []


def test_an_accounts_own_caption_follows_its_platform() -> None:
    long = "x" * 3000
    both = [_target("facebook", long, "@page"), _target("instagram", "short", "@shop")]
    assert _failing(_post(both, "short")) == []
    swapped = [_target("facebook", "short", "@page"), _target("instagram", long, "@shop")]
    assert _failing(_post(swapped, "short")) == [("caption", "targets.1.caption_override")]
    # The shared caption goes only to accounts without their own, so Instagram's own is enough.
    assert (
        _failing(_post([_target("facebook", "a", "@page"), _target("instagram", "b")], long)) == []
    )


def test_the_failure_names_the_limit_and_the_pass_line_the_posts_limit() -> None:
    items = rules.checklist(
        _post([_target("instagram")], "x" * 2300), now=NOW, publishing_limit=100
    )
    message = next(i.message for i in items if i.key == "caption" and not i.ok)
    assert message == "Shorten the caption to 2,200 characters (now 2,300)."
    page = rules.checklist(_post([_target("facebook")], "hi"), now=NOW, publishing_limit=100)
    assert next(i.message for i in page if i.key == "caption") == (
        "Caption within 63,206 characters"
    )


def test_the_request_bodies_take_the_longest_limit() -> None:
    body = ScheduledPostDraft(
        caption="x" * 63_206,
        targets=[
            TargetIn(
                social_account_id="00000000-0000-0000-0000-000000000001",
                caption_override="y" * 63_206,
            )
        ],  # type: ignore[arg-type]
    )
    assert len(body.caption) == 63_206
