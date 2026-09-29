"""Sandbox publishing (T7.2; TR-PL-07, FR-PUB-05, F-13 end to end): containers, their processing
and published posts live in memory, so the composer, the calendar and the publish jobs can be
developed and tested without Meta. The adapter's publishing methods delegate here.

Meant to behave like Instagram where the jobs depend on it: image containers are FINISHED at once;
video (Reel and carousel video children) containers stay IN_PROGRESS for a few status reads before
FINISHED; published posts get a platform media id and a permalink and show up in
``history.post`` / ``list_media`` like synced posts; a first comment gets an id. Failures (quota
used up, a container ERROR, a failed publish) are injectable for tests, like sends (see
``outbox``), and ``outbox.reset()`` forgets everything.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import (
    ContainerMedia,
    ContainerStatus,
    PlatformMedia,
    PublishingQuota,
)


def publishing_quota(acct: SocialAccount) -> PublishingQuota:
    raise NotImplementedError("T7.2")


def create_image_container(acct: SocialAccount, *, image_url: str, caption: str) -> str:
    raise NotImplementedError("T7.2")


def create_reel_container(
    acct: SocialAccount, *, video_url: str, caption: str, share_to_feed: bool
) -> str:
    raise NotImplementedError("T7.2")


def create_carousel_item(acct: SocialAccount, media: ContainerMedia) -> str:
    raise NotImplementedError("T7.2")


def create_carousel_container(acct: SocialAccount, *, children: Sequence[str], caption: str) -> str:
    raise NotImplementedError("T7.2")


def container_status(acct: SocialAccount, container_ref: str) -> ContainerStatus:
    raise NotImplementedError("T7.2")


def publish_container(acct: SocialAccount, container_ref: str) -> str:
    raise NotImplementedError("T7.2")


def published_media(acct: SocialAccount, media_ref: str) -> PlatformMedia | None:
    raise NotImplementedError("T7.2")


def find_published_media(
    acct: SocialAccount, container_ref: str, *, caption: str, published_after: datetime
) -> PlatformMedia | None:
    raise NotImplementedError("T7.2")


def post_comment(acct: SocialAccount, media_ref: str, text: str) -> str | None:
    raise NotImplementedError("T7.2")
