"""YouTube channel adapter (TR-PL-01, TR-PL-11; C-195).

A connected channel publishes and has comments; it has no DMs. The stored credential is a
Google refresh token with no expiry (``token_expires_at`` NULL), so ``refresh_token`` has nothing to
do: ``access_token`` mints a short-lived access token for each use instead.

Publishing (C-196): the upload itself is YouTube's own (services/post_publishing/youtube_*.py with
platforms/youtube/publishing.py), so the container methods that create something answer
``capability_unavailable``. Once a video exists its id is the "container": ``get_container_status``
maps YouTube's processing (``status.uploadStatus``, ``processingDetails.processingStatus``) and a
pending ``publishAt`` to the ContainerStatus codes, ``publish_container`` changes nothing (privacy
and time were set with the upload) and returns the id, ``get_published_media`` reads it back. Stats
(D5): views, likes and comments per video (videos.list, 1 unit) and the channel's subscribers.

Comments (YT4; platforms/youtube/comments.py): COMMENTS, without PRIVATE_REPLY (YouTube has no
DMs). ``list_comments`` reads one video's threads (the channel-wide poll is
services/youtube_comments.py); a reply goes under the thread's top-level comment; hiding rejects
the comment, showing it again publishes it (a refusal is ``capability_unavailable``: YouTube doesn't
let this comment be restored); deleting a viewer's comment, which YouTube forbids, rejects it
instead. ``post_comment`` stays unavailable. Only people act on YouTube comments: automations and
spam auto-hide skip YouTube (services/automations/comments.py, services/comments/analysis.py).
``list_media`` is the channel's recent uploads, so the 6-hourly media sync stores them;
``get_media`` reads one video. Both say "video": a Short published here was stored as a "reel" with
its /shorts/ link, which the media upsert keeps (repositories/ingest.upsert_media_item).

The sandbox channel (C-196) is served by this adapter too (platforms/registry.py), with
publishing.SandboxVideos and comments.SandboxComments: no Google, no token.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from socialhood.models.connections import SocialAccount
from socialhood.observability.logging import get_logger
from socialhood.platforms.base import (
    AccountInsights,
    CollaboratorStatus,
    CommentPage,
    ContactProfile,
    ContainerMedia,
    ContainerStatus,
    IceBreaker,
    MediaCounts,
    MediaDownload,
    MediaInsights,
    OutboundMessage,
    PlatformMedia,
    PlatformThread,
    PublishExtras,
    PublishingQuota,
    SendResult,
    TokenGrant,
)
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.events import InboundMediaRef
from socialhood.platforms.youtube.analytics import analytics_for
from socialhood.platforms.youtube.comments import comments_for, top_level_id
from socialhood.platforms.youtube.oauth import ANALYTICS_SCOPE, SCOPE, youtube_for
from socialhood.platforms.youtube.publishing import Video, is_sandbox_channel, videos_for

CAPABILITIES = frozenset({Capability.PUBLISH, Capability.POST_INSIGHTS, Capability.COMMENTS})
ANALYTICS_CAPABILITIES = CAPABILITIES | {Capability.ACCOUNT_INSIGHTS}
# YouTube Analytics lags about two days: a younger video has nothing to read yet.
ANALYTICS_LAG = timedelta(hours=48)
log = get_logger()
NO_MESSAGES = "YouTube channels have no direct messages"
NO_PRIVATE_REPLY = "YouTube has no private replies"
NO_COMMENTING = "Amplychat can't start a comment on YouTube"
NOT_RESTORABLE = "YouTube doesn't let this comment be restored."
OWN_UPLOAD = "YouTube videos are uploaded by the YouTube publishing step"
NOT_PROCESSED = "YouTube couldn't process the video"
GONE = "The video is no longer on YouTube."
FAILED_UPLOADS = frozenset({"failed", "rejected", "deleted"})
FAILED_PROCESSING = frozenset({"failed", "terminated"})
SANDBOX_TOKEN = "sandbox"  # noqa: S105 (the sandbox channel needs no token)


def container_status(video: Video | None, now: datetime) -> ContainerStatus:
    """A video's state as the publish jobs read a container: gone or failed is ERROR, still
    processing or waiting for its ``publishAt`` is IN_PROGRESS, else FINISHED."""
    if video is None:
        return ContainerStatus(status_code="ERROR", detail=GONE)
    if video.upload_status in FAILED_UPLOADS or video.processing in FAILED_PROCESSING:
        why = f" ({video.failure})" if video.failure else ""
        return ContainerStatus(status_code="ERROR", detail=f"{NOT_PROCESSED}{why}.")
    if video.upload_status != "processed" and video.processing != "succeeded":
        return ContainerStatus(status_code="IN_PROGRESS")
    if video.privacy == "private" and video.publish_at is not None and video.publish_at > now:
        return ContainerStatus(status_code="IN_PROGRESS")
    return ContainerStatus(status_code="FINISHED")


def published_media(video: Video, *, short: bool = False) -> PlatformMedia:
    url = (
        f"https://www.youtube.com/shorts/{video.id}"
        if short
        else f"https://www.youtube.com/watch?v={video.id}"
    )
    return PlatformMedia(
        platform_media_id=video.id,
        media_type="reel" if short else "video",
        caption=video.description or None,
        media_url=None,
        thumbnail_url=video.thumbnail_url,
        permalink=url,
        posted_at=video.published_at or datetime.now(UTC),
        like_count=video.likes,
        comments_count=video.comments,
    )


def _unavailable(message: str) -> PlatformError:
    return PlatformError("capability_unavailable", message=message)


class YouTubeAdapter:
    platform = "youtube"

    def __init__(self, deps: PlatformDeps) -> None:
        self.deps = deps

    def capabilities_for(self, acct: SocialAccount) -> frozenset[Capability]:
        if is_sandbox_channel(acct):
            return ANALYTICS_CAPABILITIES
        scopes = acct.scopes or []
        if SCOPE not in scopes:
            return frozenset()
        return ANALYTICS_CAPABILITIES if ANALYTICS_SCOPE in scopes else CAPABILITIES

    def _analytics_granted(self, acct: SocialAccount) -> bool:
        return Capability.ACCOUNT_INSIGHTS in self.capabilities_for(acct)

    async def access_token(self, acct: SocialAccount) -> str:
        """A short-lived access token minted from the stored refresh token. Google's
        ``invalid_grant`` (access removed, password changed) is ``account_needs_reconnect``."""
        if is_sandbox_channel(acct):
            return SANDBOX_TOKEN
        if acct.access_token_enc is None:
            raise PlatformError("account_needs_reconnect", message="The channel is disconnected")
        refresh = self.deps.cipher.decrypt(acct.access_token_enc)
        return await youtube_for(self.deps).access_token(refresh)

    async def refresh_token(self, acct: SocialAccount) -> TokenGrant:
        """Nothing to refresh: the stored refresh token does not expire."""
        if acct.access_token_enc is None:
            raise PlatformError("account_needs_reconnect", message="The channel is disconnected")
        return TokenGrant(self.deps.cipher.decrypt(acct.access_token_enc), None)

    async def subscribe_webhooks(self, acct: SocialAccount) -> None:
        return None  # no webhooks for a channel

    async def fetch_contact_profile(
        self, acct: SocialAccount, platform_user_id: str
    ) -> ContactProfile | None:
        return None

    async def send_message(
        self, acct: SocialAccount, recipient_ref: str, message: OutboundMessage
    ) -> SendResult:
        raise _unavailable(NO_MESSAGES)

    async def mark_read(
        self, acct: SocialAccount, recipient_ref: str, *, message_ref: str | None = None
    ) -> None:
        raise _unavailable(NO_MESSAGES)

    async def download_media(self, acct: SocialAccount, ref: InboundMediaRef) -> MediaDownload:
        raise _unavailable(NO_MESSAGES)

    async def list_media(self, acct: SocialAccount, *, limit: int = 25) -> list[PlatformMedia]:
        """The channel's newest uploads with their counts (3 units), failed ones left out."""
        videos = await videos_for(acct, self.deps).recent_uploads(
            await self.access_token(acct), acct.platform_account_id, limit=limit
        )
        return [published_media(v) for v in videos if v.upload_status not in FAILED_UPLOADS]

    async def list_stories(self, acct: SocialAccount) -> list[PlatformMedia]:
        return []

    async def get_media(self, acct: SocialAccount, media_ref: str) -> PlatformMedia | None:
        video = await self._video(acct, media_ref)
        return published_media(video) if video is not None else None

    async def set_ice_breakers(
        self, acct: SocialAccount, starters: Sequence[IceBreaker]
    ) -> list[IceBreaker]:
        raise _unavailable(NO_MESSAGES)

    async def list_threads(self, acct: SocialAccount, *, limit: int = 20) -> list[PlatformThread]:
        raise _unavailable(NO_MESSAGES)

    async def private_reply(
        self, acct: SocialAccount, comment_ref: str, message: OutboundMessage
    ) -> SendResult:
        raise _unavailable(NO_PRIVATE_REPLY)

    async def reply_to_comment(
        self, acct: SocialAccount, comment_ref: str, text: str
    ) -> str | None:
        token = await self.access_token(acct)
        return await comments_for(acct, self.deps).reply(token, top_level_id(comment_ref), text)

    async def list_comments(
        self, acct: SocialAccount, media_ref: str, *, cursor: str | None = None
    ) -> CommentPage:
        return await comments_for(acct, self.deps).threads(
            await self.access_token(acct),
            channel_id=acct.platform_account_id,
            video_id=media_ref,
            cursor=cursor,
        )

    async def hide_comment(self, acct: SocialAccount, comment_ref: str) -> None:
        token = await self.access_token(acct)
        await comments_for(acct, self.deps).moderate(token, comment_ref, "rejected")

    async def unhide_comment(self, acct: SocialAccount, comment_ref: str) -> None:
        token = await self.access_token(acct)
        try:
            await comments_for(acct, self.deps).moderate(token, comment_ref, "published")
        except PlatformError as error:
            if error.code != "platform_rejected":
                raise
            raise PlatformError(
                "capability_unavailable", platform_code=error.platform_code, message=NOT_RESTORABLE
            ) from error

    async def delete_comment(self, acct: SocialAccount, comment_ref: str) -> None:
        """The channel's own comment is deleted; a viewer's, which YouTube won't let the channel
        delete, is rejected (hidden for good) instead."""
        comments = comments_for(acct, self.deps)
        token = await self.access_token(acct)
        try:
            await comments.delete(token, comment_ref)
        except PlatformError as error:
            if error.platform_code not in ("forbidden", "403"):
                raise
            await comments.moderate(token, comment_ref, "rejected")

    async def _video(self, acct: SocialAccount, video_id: str) -> Video | None:
        return await videos_for(acct, self.deps).get(await self.access_token(acct), video_id)

    async def get_media_counts(self, acct: SocialAccount, media_ref: str) -> MediaCounts | None:
        video = await self._video(acct, media_ref)
        if video is None:
            return None
        return MediaCounts(like_count=video.likes, comments_count=video.comments)

    async def get_media_insights(
        self, acct: SocialAccount, media_ref: str, *, media_type: str
    ) -> MediaInsights:
        """D5's basic stats (videos.list statistics), plus watch time and subscribers gained from
        YouTube Analytics when granted and the video is past the lag. An Analytics failure keeps
        the basic stats."""
        video = await self._video(acct, media_ref)
        if video is None:
            return MediaInsights()
        basic = MediaInsights(views=video.views, likes=video.likes, comments=video.comments)
        now = datetime.now(UTC)
        if (
            not self._analytics_granted(acct)
            or video.published_at is None
            or now - video.published_at < ANALYTICS_LAG
        ):
            return basic
        try:
            report = await analytics_for(is_sandbox_channel(acct), self.deps).video(
                await self.access_token(acct),
                media_ref,
                since=video.published_at.date(),
                until=now.date(),
            )
        except PlatformError as error:
            log.warning("youtube_analytics_failed", error_code=error.code, scope="video")
            return basic
        return replace(
            basic,
            watch_minutes=report.watch_minutes,
            avg_view_seconds=report.avg_view_seconds,
            avg_view_percent=report.avg_view_percent,
            follows=report.subscribers_gained,
        )

    async def get_account_insights(
        self, acct: SocialAccount, day: date, *, tz: str = "UTC"
    ) -> AccountInsights:
        """The channel's subscribers as its followers (channels.list statistics), plus the day's
        views, watch time and subscribers gained and lost when Analytics is granted. A day inside
        the lag reads empty (all None, stored as {}); the daily job re-reads it later (_settle)."""
        token = await self.access_token(acct)
        count = await videos_for(acct, self.deps).subscribers(token, acct.platform_account_id)
        if not self._analytics_granted(acct):
            return AccountInsights(followers_count=count)
        try:
            report = await analytics_for(is_sandbox_channel(acct), self.deps).day(token, day)
        except PlatformError as error:
            log.warning("youtube_analytics_failed", error_code=error.code, scope="day")
            return AccountInsights(followers_count=count)
        return AccountInsights(
            followers_count=count,
            views=report.views,
            watch_minutes=report.watch_minutes,
            follows=report.subscribers_gained,
            unfollows=report.subscribers_lost,
        )

    # ---- publishing (C-196): the video id is the container

    async def get_publishing_quota(self, acct: SocialAccount) -> PublishingQuota:
        raise _unavailable("YouTube has no per-channel publishing limit to read")

    async def create_image_container(
        self,
        acct: SocialAccount,
        *,
        image_url: str,
        caption: str,
        extras: PublishExtras | None = None,
    ) -> str:
        raise _unavailable(OWN_UPLOAD)

    async def create_reel_container(
        self,
        acct: SocialAccount,
        *,
        video_url: str,
        caption: str,
        share_to_feed: bool = True,
        page_reel: bool = False,
        extras: PublishExtras | None = None,
    ) -> str:
        raise _unavailable(OWN_UPLOAD)

    async def create_story_container(self, acct: SocialAccount, media: ContainerMedia) -> str:
        raise _unavailable(OWN_UPLOAD)

    async def create_carousel_item(self, acct: SocialAccount, media: ContainerMedia) -> str:
        raise _unavailable(OWN_UPLOAD)

    async def create_carousel_container(
        self,
        acct: SocialAccount,
        *,
        children: Sequence[str],
        caption: str,
        extras: PublishExtras | None = None,
    ) -> str:
        raise _unavailable(OWN_UPLOAD)

    async def list_collaborators(
        self, acct: SocialAccount, media_ref: str
    ) -> list[CollaboratorStatus]:
        return []

    async def get_container_status(
        self, acct: SocialAccount, container_ref: str
    ) -> ContainerStatus:
        return container_status(await self._video(acct, container_ref), datetime.now(UTC))

    async def create_text_container(self, acct: SocialAccount) -> str:
        raise _unavailable(OWN_UPLOAD)

    async def publish_container(
        self, acct: SocialAccount, container_ref: str, *, caption: str = ""
    ) -> str:
        """Nothing to do: the privacy (and ``publishAt``) went with the upload."""
        return container_ref

    async def get_published_media(
        self, acct: SocialAccount, media_ref: str, *, story: bool = False
    ) -> PlatformMedia | None:
        video = await self._video(acct, media_ref)
        return published_media(video) if video is not None else None

    async def find_published_media(
        self,
        acct: SocialAccount,
        container_ref: str,
        *,
        caption: str,
        published_after: datetime,
        story: bool = False,
    ) -> PlatformMedia | None:
        """The container is the video: read it (YouTube never answers PUBLISHED here)."""
        return await self.get_published_media(acct, container_ref)

    async def post_comment(self, acct: SocialAccount, media_ref: str, text: str) -> str | None:
        raise _unavailable(NO_COMMENTING)
