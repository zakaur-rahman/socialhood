"""The Instagram extras of a post as the adapter takes them (FR-PUB-07, C-134): collaborators, the
location, user tags and a Reel's cover and audio name. Only an Instagram account gets them, and
never a Story (Meta: collaborators are for feed images, Reels and carousels; a Story container
here is sent as before)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from socialhood.models.connections import SocialAccount
from socialhood.models.publishing import PostFormat, ScheduledPost
from socialhood.platforms.base import PublishExtras, UserTag


def user_tags(rows: Sequence[dict[str, Any]] | None) -> tuple[UserTag, ...]:
    """Stored tags ([{username, x, y}]) as the adapter takes them."""
    return tuple(
        UserTag(username=str(r["username"]), x=float(r["x"]), y=float(r["y"]))
        for r in rows or ()
        if r.get("username")
    )


def applies(post: ScheduledPost, acct: SocialAccount) -> bool:
    return acct.platform == "instagram" and post.format not in (PostFormat.STORY, PostFormat.TEXT)


def extras_for(
    post: ScheduledPost,
    acct: SocialAccount,
    *,
    tags: tuple[UserTag, ...] = (),
    cover_url: str | None = None,
) -> PublishExtras | None:
    """None when the account takes none or the post sets none. ``tags``: a single image's own
    tags; a Reel's cover and audio name only go on a Reel."""
    if not applies(post, acct):
        return None
    reel = post.format == PostFormat.REEL
    extras = PublishExtras(
        collaborators=tuple(post.collaborators or ()),
        location_id=post.location_id or None,
        user_tags=tags if post.format == PostFormat.IMAGE else (),
        cover_url=cover_url if reel else None,
        thumb_offset_ms=post.cover_offset_ms if reel else None,
        audio_name=(post.audio_name or None) if reel else None,
    )
    empty = PublishExtras()
    return None if extras == empty else extras
