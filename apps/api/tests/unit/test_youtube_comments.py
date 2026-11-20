"""YT4: YouTube comments - commentThreads JSON as comments, the reply's parent, the adapter's
comment calls against the fake (reply, hide, unhide refused, delete falling back to rejecting),
the sandbox seed, the daily-units rule and the "important" rule."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from socialhood.models.analytics import CommentAnalysis
from socialhood.models.automations import Comment
from socialhood.models.connections import SocialAccount
from socialhood.platforms.buckets import (
    YOUTUBE_POLL_CEILING,
    YOUTUBE_READ_UNITS,
    YOUTUBE_WRITE_CEILING,
    YOUTUBE_WRITE_UNITS,
    fits,
)
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.youtube.adapter import NOT_RESTORABLE, YouTubeAdapter
from socialhood.platforms.youtube.comments import (
    SANDBOX_COMMENT,
    SANDBOX_VIEWER,
    SandboxComments,
    page_from,
    thread_comments,
    top_level_id,
)
from socialhood.platforms.youtube.fake import CHANNEL, FakeYouTube
from socialhood.platforms.youtube.oauth import SCOPE
from socialhood.security.crypto import TokenCipher, new_key
from socialhood.services.comments.queries import IMPORTANT_LIKES, is_important

KEY = new_key()


def snippet(**values: Any) -> dict[str, Any]:
    return {
        "videoId": "vid1",
        "authorDisplayName": "Asha",
        "authorChannelId": {"value": "UCasha"},
        "textDisplay": "Where can I buy this?",
        "textOriginal": "Where can I buy this?",
        "likeCount": 3,
        "publishedAt": "2026-11-10T08:00:00Z",
        **values,
    }


def thread(**values: Any) -> dict[str, Any]:
    return {
        "id": "Ugtop",
        "snippet": {
            "channelId": "UCme",
            "videoId": "vid1",
            "topLevelComment": {"id": "Ugtop", "snippet": snippet()},
            **values,
        },
        "replies": {
            "comments": [
                {
                    "id": "Ugtop.r1",
                    "snippet": snippet(
                        authorDisplayName="Ben",
                        authorChannelId={"value": "UCben"},
                        textOriginal=None,
                        textDisplay="Same question",
                        likeCount=0,
                        parentId="Ugtop",
                    ),
                }
            ]
        },
    }


def test_a_thread_is_its_top_level_comment_then_its_replies() -> None:
    top, reply = thread_comments(thread())
    assert (top.platform_comment_id, top.parent_id, top.media_id) == ("Ugtop", None, "vid1")
    assert (top.author_ref, top.author_username, top.text) == (
        "UCasha",
        "Asha",
        "Where can I buy this?",
    )
    assert (top.like_count, top.account_ref) == (3, "UCme")
    assert top.occurred_at == datetime(2026, 11, 10, 8, tzinfo=UTC)
    assert (reply.platform_comment_id, reply.parent_id, reply.author_ref) == (
        "Ugtop.r1",
        "Ugtop",
        "UCben",
    )
    assert reply.text == "Same question"  # textDisplay when textOriginal is missing


def test_channel_discussion_and_authorless_comments_are_skipped() -> None:
    assert thread_comments(thread(videoId=None)) == []
    no_author = thread(topLevelComment={"id": "Ugx", "snippet": snippet(authorChannelId=None)})
    assert thread_comments(no_author) == []
    page = page_from({"items": [thread(), thread(videoId=None)], "nextPageToken": "n2"})
    assert [c.platform_comment_id for c in page.comments] == ["Ugtop", "Ugtop.r1"]
    assert page.next_cursor == "n2"
    assert page_from({"items": []}).next_cursor is None


def test_a_reply_goes_under_the_thread_s_top_level_comment() -> None:
    assert top_level_id("Ugtop") == "Ugtop"
    assert top_level_id("Ugtop.r1") == "Ugtop"
    assert top_level_id("Ugtop.r1.x") == "Ugtop"


# ---------------------------------------------------------------- the adapter on the fake


def deps() -> PlatformDeps:
    settings = SimpleNamespace(youtube_workspaces="", sandbox_platform_enabled=False)
    return PlatformDeps(http=MagicMock(), cipher=TokenCipher([KEY]), settings=settings)  # type: ignore[arg-type]


def channel(platform_account_id: str = CHANNEL.id) -> SocialAccount:
    return SocialAccount(
        id=uuid.uuid4(),
        platform="youtube",
        platform_account_id=platform_account_id,
        status="active",
        scopes=[SCOPE],
        access_token_enc=TokenCipher([KEY]).encrypt("fake-yt-refresh:1"),
    )


async def test_the_adapter_reads_replies_and_moderates(fake_youtube: FakeYouTube) -> None:
    store = fake_youtube.comment_threads
    top = store.add("vid1", "Price?", likes=12)
    reply = store.add("vid1", "Me too", parent_id=top)
    adapter = YouTubeAdapter(deps())

    page = await adapter.list_comments(channel(), "vid1")
    assert [(c.platform_comment_id, c.parent_id) for c in page.comments] == [
        (top, None),
        (reply, top),
    ]
    assert fake_youtube.named("comment_threads")[0]["video_id"] == "vid1"

    answered = await adapter.reply_to_comment(channel(), reply, "₹499")
    assert fake_youtube.named("reply_comment")[0]["parent_id"] == top  # the thread, not the reply
    assert (answered or "").startswith(f"{top}.")

    await adapter.hide_comment(channel(), top)
    assert store.items[top].status == "rejected"
    fake_youtube.fail_on(
        "moderate_comment", PlatformError("platform_rejected", platform_code="processingFailure")
    )
    with pytest.raises(PlatformError) as refused:
        await adapter.unhide_comment(channel(), top)
    assert (refused.value.code, refused.value.message) == ("capability_unavailable", NOT_RESTORABLE)


async def test_deleting_a_viewer_s_comment_rejects_it_instead(fake_youtube: FakeYouTube) -> None:
    store = fake_youtube.comment_threads
    viewer = store.add("vid1", "spam spam")
    adapter = YouTubeAdapter(deps())

    await adapter.delete_comment(channel(), viewer)

    assert [a["comment_id"] for a in fake_youtube.named("delete_comment")] == [viewer]
    assert store.items[viewer].status == "rejected"
    own = await adapter.reply_to_comment(channel(), viewer, "Please stop")
    assert own is not None
    await adapter.delete_comment(channel(), own)  # the channel's own: really deleted
    assert own not in store.items


async def test_media_reads_are_the_channel_s_videos(fake_youtube: FakeYouTube) -> None:
    adapter = YouTubeAdapter(deps())
    assert await adapter.get_media(channel(), "nope") is None
    session = await fake_youtube.open_session(
        "fake-yt-access:fake-yt-refresh:1",
        metadata={"title": "Bread", "privacy": "public"},
        size=1,
        content_type="video/mp4",
    )
    video = fake_youtube.finish_upload(session)
    [listed] = await adapter.list_media(channel())
    assert (listed.platform_media_id, listed.media_type) == (video.id, "video")
    assert listed.permalink == f"https://www.youtube.com/watch?v={video.id}"
    got = await adapter.get_media(channel(), video.id)
    assert got is not None
    assert got.platform_media_id == video.id


async def test_the_sandbox_seeds_one_viewer_comment_per_video() -> None:
    sandbox = SandboxComments()
    page = await sandbox.threads("sandbox", channel_id="sandbox_yt", video_id="sandbox_yt_abc")
    [seeded] = page.comments
    assert seeded.platform_comment_id == SANDBOX_COMMENT + "sandbox_yt_abc"
    assert (seeded.author_ref, seeded.like_count >= IMPORTANT_LIKES) == (SANDBOX_VIEWER, True)
    assert (await sandbox.threads("sandbox", channel_id="sandbox_yt")).comments == ()
    assert (await sandbox.reply("sandbox", seeded.platform_comment_id, "hi")).startswith(
        seeded.platform_comment_id + "."
    )


# ---------------------------------------------------------------- daily units


def test_polling_stops_at_8000_units_and_writes_at_9500() -> None:
    assert fits(7_999, YOUTUBE_READ_UNITS, YOUTUBE_POLL_CEILING)
    assert not fits(8_000, YOUTUBE_READ_UNITS, YOUTUBE_POLL_CEILING)
    assert fits(9_450, YOUTUBE_WRITE_UNITS, YOUTUBE_WRITE_CEILING)
    assert not fits(9_451, YOUTUBE_WRITE_UNITS, YOUTUBE_WRITE_CEILING)


# ---------------------------------------------------------------- important


def comment(**values: Any) -> Comment:
    base: dict[str, Any] = {
        "like_count": 0,
        "hidden": False,
        "deleted_at": None,
        "our_replied_at": None,
        "private_reply_message_id": None,
        "analysis_status": "done",
    }
    return Comment(**(base | values))


def analysis(**values: Any) -> CommentAnalysis:
    return CommentAnalysis(
        **({"sentiment": "neutral", "intent": "feedback", "is_spam": False} | values)
    )


@pytest.mark.parametrize(
    ("row", "read", "important"),
    [
        ({}, {"intent": "pricing"}, True),  # a question
        ({}, {"intent": "purchase"}, True),  # buying
        ({}, {"sentiment": "negative"}, True),
        ({}, {}, False),
        ({"like_count": 10}, {}, True),
        ({"like_count": 10, "analysis_status": "pending"}, None, True),  # likes need no analysis
        ({"analysis_status": "pending"}, {"intent": "pricing"}, False),  # not read yet
        ({"like_count": 50}, {"is_spam": True}, False),
        ({"hidden": True}, {"intent": "pricing"}, False),
        ({"deleted_at": datetime.now(UTC)}, {"intent": "pricing"}, False),
        ({"our_replied_at": datetime.now(UTC)}, {"intent": "pricing"}, False),
        ({"private_reply_message_id": uuid.uuid4()}, {"sentiment": "negative"}, False),
    ],
)
def test_the_important_rule(
    row: dict[str, Any], read: dict[str, Any] | None, important: bool
) -> None:
    found = analysis(**read) if read is not None else None
    assert is_important(comment(**row), found) is important
