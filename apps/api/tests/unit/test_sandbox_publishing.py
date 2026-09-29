"""T7.2 (TR-PL-07): sandbox publishing behaves like Instagram where the publish jobs depend on it:
videos process for a few status reads, a carousel needs FINISHED children of its account, a
container publishes once, the quota counts published posts, and failures are injectable."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import ContainerMedia
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.sandbox import history, outbox
from socialhood.platforms.sandbox import publishing as sandbox

ACCT = SocialAccount(platform="instagram", platform_account_id="sandbox_unit01", username="u")
OTHER = SocialAccount(platform="instagram", platform_account_id="sandbox_unit02", username="o")
IMAGE = ContainerMedia(kind="image", url="https://x/i.jpg")
VIDEO = ContainerMedia(kind="video", url="https://x/v.mp4")


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    outbox.reset()
    yield
    outbox.reset()


def test_a_video_processes_for_a_few_reads() -> None:
    sandbox.processing_reads(2)
    reel = sandbox.create_reel_container(ACCT, video_url=VIDEO.url, caption="", share_to_feed=True)
    codes = [sandbox.container_status(ACCT, reel).status_code for _ in range(3)]
    assert codes == ["IN_PROGRESS", "IN_PROGRESS", "FINISHED"]
    image = sandbox.create_image_container(ACCT, image_url=IMAGE.url, caption="")
    assert sandbox.container_status(ACCT, image).status_code == "FINISHED"


def test_a_carousel_needs_finished_children_of_its_account() -> None:
    sandbox.processing_reads(1)
    image = sandbox.create_carousel_item(ACCT, IMAGE)
    video = sandbox.create_carousel_item(ACCT, VIDEO)
    with pytest.raises(PlatformError, match="still processing"):
        sandbox.create_carousel_container(ACCT, children=[image, video], caption="")
    sandbox.container_status(ACCT, video)
    sandbox.container_status(ACCT, video)
    theirs = sandbox.create_carousel_item(OTHER, IMAGE)
    with pytest.raises(PlatformError):
        sandbox.create_carousel_container(ACCT, children=[image, theirs], caption="")
    with pytest.raises(PlatformError):
        sandbox.create_carousel_container(ACCT, children=[image], caption="")
    carousel = sandbox.create_carousel_container(ACCT, children=[image, video], caption="Menu")
    media_id = sandbox.publish_container(ACCT, carousel)
    media = sandbox.published_media(ACCT, media_id)
    assert media is not None
    assert (media.media_type, media.caption) == ("carousel", "Menu")
    with pytest.raises(PlatformError):  # children are published through their carousel
        sandbox.publish_container(ACCT, image)


def test_a_container_publishes_once() -> None:
    container = sandbox.create_image_container(ACCT, image_url=IMAGE.url, caption="Once")
    sandbox.publish_container(ACCT, container)
    assert sandbox.container_status(ACCT, container).status_code == "PUBLISHED"
    with pytest.raises(PlatformError, match="already published"):
        sandbox.publish_container(ACCT, container)
    assert sandbox.publish_count() == 1


def test_the_quota_counts_published_posts_and_blocks_at_the_limit() -> None:
    sandbox.set_quota(1, 2)
    first = sandbox.create_image_container(ACCT, image_url=IMAGE.url, caption="")
    sandbox.publish_container(ACCT, first)
    quota = sandbox.publishing_quota(ACCT)
    assert (quota.used, quota.limit, quota.remaining) == (2, 2, 0)
    second = sandbox.create_image_container(ACCT, image_url=IMAGE.url, caption="")
    with pytest.raises(PlatformError, match="daily publishing limit"):
        sandbox.publish_container(ACCT, second)


def test_a_lost_answer_still_publishes_and_is_found() -> None:
    sandbox.lose_next_publish_answer()
    container = sandbox.create_image_container(ACCT, image_url=IMAGE.url, caption="Lost  one")
    before = datetime.now(UTC) - timedelta(seconds=5)
    with pytest.raises(PlatformError) as caught:
        sandbox.publish_container(ACCT, container)
    assert caught.value.code == "delivery_unknown"
    assert not caught.value.retryable
    found = sandbox.find_published_media(
        ACCT, container, caption="Lost one", published_after=before
    )
    row = sandbox.container(container)
    assert found is not None
    assert row is not None
    assert found.platform_media_id == row.media_id
    assert history.post(ACCT, found.platform_media_id).caption == "Lost  one"


def test_failures_are_injectable_per_step_and_by_caption() -> None:
    sandbox.fail_next("platform_unavailable", step="status")
    container = sandbox.create_image_container(ACCT, image_url=IMAGE.url, caption="")
    with pytest.raises(PlatformError) as caught:
        sandbox.container_status(ACCT, container)
    assert caught.value.retryable
    assert sandbox.container_status(ACCT, container).status_code == "FINISHED"

    doomed = sandbox.create_image_container(
        ACCT, image_url=IMAGE.url, caption="Hi [sandbox:fail=platform_rejected]"
    )
    for _ in range(2):  # every attempt
        with pytest.raises(PlatformError):
            sandbox.publish_container(ACCT, doomed)

    sandbox.fail_next_container("ERROR", "Bad video")
    broken = sandbox.create_reel_container(
        ACCT, video_url=VIDEO.url, caption="", share_to_feed=True
    )
    status = sandbox.container_status(ACCT, broken)
    assert (status.status_code, status.detail) == ("ERROR", "Bad video")


def test_published_posts_come_first_and_seeded_ones_stay_findable() -> None:
    container = sandbox.create_image_container(ACCT, image_url=IMAGE.url, caption="New")
    media_id = sandbox.publish_container(ACCT, container)
    listed = history.posts(ACCT, limit=3)
    assert [p.platform_media_id for p in listed] == [
        media_id,
        "sandbox_unit01_post_0",
        "sandbox_unit01_post_1",
    ]
    last_seeded = history.post(ACCT, "sandbox_unit01_post_2")
    assert last_seeded.caption == history.POSTS[2][1]


def test_comments_are_recorded() -> None:
    comment_id = sandbox.post_comment(ACCT, "sandbox_media_1", "#tags")
    [comment] = list(sandbox.COMMENTS)
    assert (comment.platform_comment_id, comment.text) == (comment_id, "#tags")
    with pytest.raises(PlatformError):
        sandbox.post_comment(ACCT, "sandbox_media_1", "[sandbox:fail=platform_rejected]")


def test_reset_forgets_everything() -> None:
    container = sandbox.create_image_container(ACCT, image_url=IMAGE.url, caption="")
    sandbox.publish_container(ACCT, container)
    sandbox.fail_next("platform_rejected", step="publish")
    outbox.reset()
    assert sandbox.container(container) is None
    assert sandbox.published(ACCT.platform_account_id) == []
    assert sandbox.publish_count() == 0
    assert not sandbox.STATE.failures
