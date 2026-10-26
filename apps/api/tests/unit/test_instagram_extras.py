"""FR-PUB-07 (C-134): Instagram collaborators, user tags, the location and a Reel's options, without
a database: parsing usernames and locations, the checklist's rules and messages, the container
payloads, the sandbox's behaviour and the collaborator invite parsing."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from socialhood.models.connections import SocialAccount
from socialhood.models.publishing import PostFormat
from socialhood.platforms.base import ContainerMedia, PublishExtras, UserTag
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.instagram import parse, publishing
from socialhood.platforms.sandbox import outbox
from socialhood.platforms.sandbox import publishing as sandbox
from socialhood.services.post_publishing import collaborators, extras
from socialhood.services.scheduled_posts import rules
from socialhood.services.scheduled_posts.rules import (
    AssetFacts,
    PostFacts,
    ReelFacts,
    TargetFacts,
)

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
MB = 1024 * 1024
ACCT = SocialAccount(platform="instagram", platform_account_id="sandbox_ext01", username="u")


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    outbox.reset()
    yield
    outbox.reset()


def _image(tags: int = 0, **values: Any) -> AssetFacts:
    base: dict[str, Any] = {
        "resource_type": "image",
        "format": "jpg",
        "bytes": 200_000,
        "width": 1080,
        "height": 1350,
        "duration_s": None,
        "user_tags": tags,
    }
    return AssetFacts(**{**base, **values})


def _video(duration_s: float = 20.0, **values: Any) -> AssetFacts:
    base: dict[str, Any] = {
        "resource_type": "video",
        "format": "mp4",
        "bytes": 20 * MB,
        "width": 1080,
        "height": 1920,
        "duration_s": duration_s,
    }
    return AssetFacts(**{**base, **values})


def _post(**values: Any) -> PostFacts:
    base: dict[str, Any] = {
        "targets": [
            TargetFacts(
                handle="@maple.bakery",
                status="active",
                can_publish=True,
                caption_override=None,
                recent_posts=0,
            )
        ],
        "assets": [_image()],
        "caption": "Fresh bread",
        "first_comment": None,
        "publish_at": NOW + timedelta(hours=1),
    }
    return PostFacts(**{**base, **values})


def _extras(post: PostFacts) -> list[tuple[bool, str, str | None]]:
    items = rules.checklist(post, now=NOW, publishing_limit=100)
    return [(i.ok, i.message, i.field) for i in items if i.key == "extras"]


# ---------------------------------------------------------------- parsing


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("@Maple.Bakery", "maple.bakery"),
        (" maple_2 ", "maple_2"),
        ("a" * 30, "a" * 30),
        ("a" * 31, None),
        ("bad name", None),
        ("@", None),
        ("", None),
        ("emoji\U0001f600", None),
    ],
)
def test_usernames_are_normalised_or_refused(raw: str, expected: str | None) -> None:
    assert rules.normalize_username(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("123456789012345", "123456789012345"),
        ("https://www.facebook.com/profile.php?id=100064123456789", "100064123456789"),
        ("https://www.facebook.com/profile.php?id=100064123456789&sk=about", "100064123456789"),
        ("https://facebook.com/pages/Maple-Bakery/108123456789012", "108123456789012"),
        ("https://www.facebook.com/Maple-Bakery-108123456789012/", "108123456789012"),
        ("https://www.facebook.com/maplebakery", None),
        ("1234", None),
        ("not a link", None),
        ("https://example.com/profile.php?id=123456789", None),
    ],
)
def test_a_location_is_a_page_id_or_a_link_with_one(raw: str, expected: str | None) -> None:
    assert rules.parse_location(raw) == expected


# ---------------------------------------------------------------- the checklist


def test_a_post_without_extras_lists_none() -> None:
    assert _extras(_post()) == []


def test_collaborators_up_to_three_pass() -> None:
    items = _extras(_post(collaborators=["@a.one", "b_two", "c"]))
    assert items == [(True, "Collaborators: @a.one, @b_two, @c", None)]


def test_four_collaborators_fail_with_the_count() -> None:
    items = _extras(_post(collaborators=["a", "b", "c", "d"]))
    assert items == [(False, "Add at most 3 collaborators (now 4).", "collaborators")]


def test_a_repeated_collaborator_counts_once() -> None:
    assert _extras(_post(collaborators=["a", "@A", "b", "c"]))[0][0] is True


def test_an_invalid_collaborator_username_is_named() -> None:
    items = _extras(_post(collaborators=["bad name"]))
    assert items == [(False, "bad name is not a valid Instagram username.", "collaborators")]


def test_collaborators_are_refused_on_a_story_and_without_instagram() -> None:
    story = _extras(_post(collaborators=["a"], story=True))
    assert story == [
        (
            False,
            "Collaborators are not available on Stories. Remove them or publish a post.",
            "collaborators",
        )
    ]
    page = _post(
        collaborators=["a"],
        targets=[
            TargetFacts(
                handle="Maple Page",
                status="active",
                can_publish=True,
                caption_override=None,
                recent_posts=0,
                platform="facebook",
            )
        ],
    )
    assert _extras(page) == [
        (
            False,
            "Collaborators are an Instagram feature. Choose an Instagram account or remove them.",
            "collaborators",
        )
    ]


def test_user_tags_are_counted_and_limited_per_photo() -> None:
    assert _extras(_post(assets=[_image(tags=2), _image(tags=1)])) == [
        (True, "3 tags on 2 photos", None)
    ]
    items = _extras(_post(assets=[_image(), _image(tags=21)]))
    assert items == [(False, "Tag at most 20 accounts in one photo (now 21).", "asset_ids.1")]


def test_user_tags_are_refused_on_a_story() -> None:
    items = _extras(_post(assets=[_image(tags=1)], story=True))
    assert items[0][0] is False
    assert items[0][2] == "asset_ids"


def test_a_location_must_be_a_page_id() -> None:
    assert _extras(_post(location_id="108123456789012")) == [(True, "Location set", None)]
    assert _extras(_post(location_id="maplebakery")) == [(False, rules.LOCATION_HELP, "location")]
    assert _extras(_post(location_id="1081234", story=True))[0][0] is False


def test_reel_options_pass_on_a_single_video() -> None:
    post = _post(
        assets=[_video(30.0)],
        reel_options=ReelFacts(cover=_image(), audio_name="Morning bake", share_to_feed=False),
    )
    assert _extras(post) == [(True, "Reel options set", None)]


def test_reel_options_need_a_single_video_for_instagram() -> None:
    options = ReelFacts(audio_name="x")
    assert _extras(_post(reel_options=options))[0] == (
        False,
        rules.REEL_OPTIONS_ONLY_REEL,
        "cover_asset_id",
    )
    assert _extras(_post(assets=[_video()], story=True, reel_options=options))[0][0] is False


def test_reel_cover_problems_are_named() -> None:
    video = _video(10.0)
    big = _image(bytes=9 * MB)
    options = ReelFacts(cover=big, cover_offset_ms=11_000, audio_name="x" * 101)
    items = _extras(_post(assets=[video], reel_options=options))
    assert [(msg, field) for ok, msg, field in items if not ok] == [
        ("The cover image can be up to 8 MB.", "cover_asset_id"),
        ("The cover frame is past the end of the video.", "cover_offset_ms"),
        ("Keep the audio name to 100 characters.", "audio_name"),
    ]


def test_share_to_feed_on_alone_is_not_an_option() -> None:
    assert not ReelFacts().used
    assert ReelFacts(share_to_feed=False).used


# ---------------------------------------------------------------- Reel length and size


def test_an_instagram_reel_runs_three_seconds_to_fifteen_minutes() -> None:
    def problem(seconds: float, **flags: Any) -> str | None:
        return rules.asset_problem(_video(seconds), **flags)

    assert problem(600, ig_reel=True) is None
    assert problem(900, ig_reel=True) is None
    assert problem(901, ig_reel=True) == "Reels can be up to 15 minutes."
    assert problem(2.0, ig_reel=True) == "Reels must be at least 3 seconds."
    # a carousel video, a Facebook video and Stories keep their own limits
    assert problem(91) == "Videos can be up to 90 seconds."
    assert problem(61, story=True) == "Story videos can be up to 60 seconds."


def test_the_video_size_cap_is_the_setting() -> None:
    big = _video(20.0, bytes=150 * MB)
    assert rules.asset_problem(big) == "Videos can be up to 100 MB."
    assert rules.asset_problem(big, video_max_bytes=200 * MB) is None
    post = _post(assets=[big], video_max_bytes=200 * MB)
    items = rules.checklist(post, now=NOW, publishing_limit=100)
    assert all(i.ok for i in items if i.key == "media_files")


# ---------------------------------------------------------------- what the adapter is given


def _post_row(**values: Any) -> Any:
    base: dict[str, Any] = {
        "format": PostFormat.IMAGE,
        "collaborators": ["a", "b"],
        "location_id": "108123456789012",
        "cover_offset_ms": 2500,
        "audio_name": "Morning bake",
    }
    return SimpleNamespace(**{**base, **values})


def test_extras_for_an_image_carry_collaborators_location_and_tags() -> None:
    tags = extras.user_tags([{"username": "c", "x": 0.25, "y": 0.5}])
    got = extras.extras_for(_post_row(), ACCT, tags=tags, cover_url="https://x/c.jpg")
    assert got == PublishExtras(
        collaborators=("a", "b"),
        location_id="108123456789012",
        user_tags=(UserTag(username="c", x=0.25, y=0.5),),
    )


def test_extras_for_a_reel_carry_the_cover_and_audio_name_not_tags() -> None:
    row = _post_row(format=PostFormat.REEL)
    tags = (UserTag(username="c", x=0.1, y=0.1),)
    got = extras.extras_for(row, ACCT, tags=tags, cover_url="https://x/c.jpg")
    assert got is not None
    assert got.user_tags == ()
    assert (got.cover_url, got.thumb_offset_ms, got.audio_name) == (
        "https://x/c.jpg",
        2500,
        "Morning bake",
    )


def test_extras_are_not_given_to_a_story_a_page_or_an_empty_post() -> None:
    assert extras.extras_for(_post_row(format=PostFormat.STORY), ACCT) is None
    page = SocialAccount(platform="facebook", platform_account_id="1", username="p")
    assert extras.extras_for(_post_row(), page) is None
    empty = _post_row(collaborators=[], location_id=None, cover_offset_ms=None, audio_name=None)
    assert extras.extras_for(empty, ACCT) is None


def test_the_container_body_has_only_what_is_set() -> None:
    assert publishing._with_extras({"image_url": "u"}, None) == {"image_url": "u"}
    body = publishing._with_extras(
        {"image_url": "u"},
        PublishExtras(
            collaborators=("a", "b"),
            location_id="108",
            user_tags=(UserTag(username="c", x=0.25, y=0.5),),
        ),
        tags=True,
    )
    assert body == {
        "image_url": "u",
        "collaborators": ["a", "b"],
        "location_id": "108",
        "user_tags": [{"username": "c", "x": 0.25, "y": 0.5}],
    }
    # a carousel container takes no user tags; its children carry them
    parent = publishing._with_extras(
        {"media_type": "CAROUSEL"},
        PublishExtras(collaborators=("a",), user_tags=(UserTag(username="c", x=0, y=0),)),
    )
    assert "user_tags" not in parent


def test_a_reel_cover_image_wins_over_a_frame() -> None:
    both = PublishExtras(cover_url="https://x/c.jpg", thumb_offset_ms=1000, audio_name="Mix")
    body = publishing._with_extras({"media_type": "REELS"}, both, reel=True)
    assert body["cover_url"] == "https://x/c.jpg"
    assert "thumb_offset" not in body
    assert body["audio_name"] == "Mix"
    frame = publishing._with_extras(
        {"media_type": "REELS"}, PublishExtras(thumb_offset_ms=0), reel=True
    )
    assert frame["thumb_offset"] == 0


@pytest.mark.parametrize(
    ("message", "needle"),
    [
        ("INSTAGRAM_PLATFORM_API__INVALID_LOCATION_ID", "location"),
        ("Invalid parameter: collaborators", "collaborator"),
        ("user_tags is invalid", "tag"),
    ],
)
def test_meta_refusals_about_the_extras_get_readable_reasons(message: str, needle: str) -> None:
    error = PlatformError("platform_rejected", platform_code="100/33", message=message)
    refined = publishing._refine(error)
    assert refined.message != message
    assert needle in (refined.message or "").lower()


def test_an_unrelated_refusal_is_left_alone() -> None:
    error = PlatformError("platform_rejected", platform_code="100/33", message="Something else")
    assert publishing._refine(error) is error


def test_collaborator_invites_are_parsed() -> None:
    body = {
        "data": [
            {"id": "1", "username": "Maple.One", "invite_status": "Accepted"},
            {"id": "2", "username": "two", "invite_status": "Pending"},
            {"id": "3", "username": "three"},
            {"id": "4"},
        ]
    }
    got = parse.collaborators(body)
    assert [(c.username, c.status) for c in got] == [
        ("Maple.One", "accepted"),
        ("two", "pending"),
        ("three", "pending"),
    ]


# ---------------------------------------------------------------- the sandbox


def test_the_sandbox_keeps_what_the_container_was_made_with() -> None:
    wanted = PublishExtras(
        collaborators=("a",),
        location_id="108123456789012",
        user_tags=(UserTag(username="b", x=0.5, y=0.5),),
    )
    container = sandbox.create_image_container(
        ACCT, image_url="https://x/i.jpg", caption="", extras=wanted
    )
    row = sandbox.container(container)
    assert row is not None
    assert row.extras == wanted


def test_the_sandbox_refuses_what_meta_refuses() -> None:
    with pytest.raises(PlatformError):
        sandbox.create_image_container(
            ACCT,
            image_url="u",
            caption="",
            extras=PublishExtras(collaborators=("a", "b", "c", "d")),
        )
    with pytest.raises(PlatformError, match="LOCATION"):
        sandbox.create_image_container(
            ACCT, image_url="u", caption="", extras=PublishExtras(location_id="maple")
        )
    with pytest.raises(PlatformError):
        sandbox.create_image_container(
            ACCT,
            image_url="u",
            caption="",
            extras=PublishExtras(user_tags=(UserTag(username="b", x=1.5, y=0.5),)),
        )
    with pytest.raises(PlatformError):
        sandbox.create_carousel_item(
            ACCT,
            replace(
                ContainerMedia(kind="video", url="https://x/v.mp4"),
                user_tags=(UserTag(username="b", x=0.1, y=0.1),),
            ),
        )


def test_the_sandbox_answers_invite_statuses_after_publishing() -> None:
    wanted = PublishExtras(collaborators=("pending.one", "accepts.two"))
    container = sandbox.create_image_container(ACCT, image_url="u", caption="", extras=wanted)
    media_id = sandbox.publish_container(ACCT, container)
    got = {c.username: c.status for c in sandbox.list_collaborators(ACCT, media_id)}
    assert got == {"pending.one": "pending", "accepts.two": "accepted"}
    sandbox.accept_collaborator(media_id, "pending.one")
    again = {c.username: c.status for c in sandbox.list_collaborators(ACCT, media_id)}
    assert again["pending.one"] == "accepted"


def test_a_carousel_child_keeps_its_tags() -> None:
    tags = (UserTag(username="b", x=0.2, y=0.3),)
    child = sandbox.create_carousel_item(
        ACCT, ContainerMedia(kind="image", url="u", user_tags=tags)
    )
    row = sandbox.container(child)
    assert row is not None
    assert row.user_tags == tags


# ---------------------------------------------------------------- the invite job's rules


def _target(**values: Any) -> Any:
    base: dict[str, Any] = {
        "status": "published",
        "platform_media_id": "m1",
        "collaborator_statuses": [{"username": "a", "status": "pending"}],
        "published_at": NOW - timedelta(hours=5),
        "collaborators_checked_at": None,
    }
    return SimpleNamespace(**{**base, **values})


def test_invites_are_read_hourly_for_three_days() -> None:
    assert collaborators.is_due(_target(), NOW)
    assert not collaborators.is_due(
        _target(collaborators_checked_at=NOW - timedelta(minutes=30)), NOW
    )
    assert collaborators.is_due(_target(collaborators_checked_at=NOW - timedelta(hours=1)), NOW)
    assert not collaborators.is_due(_target(published_at=NOW - timedelta(days=4)), NOW)
    assert not collaborators.is_due(_target(collaborator_statuses=[]), NOW)
    assert not collaborators.is_due(_target(status="failed"), NOW)
