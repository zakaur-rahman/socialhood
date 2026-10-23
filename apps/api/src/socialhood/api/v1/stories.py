"""Stories and story mentions (GR-06, GR-07): the account's live stories for the automation
editor's story picker (read from Instagram on each request, never stored), and the Mentions list.
The rules are in services/story_mentions.py. Stories: owners and admins (they set up automations);
mentions: any member. Another workspace's account is 404 not_found."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, Request

from socialhood.auth.deps import Admin, AnyMember, Session
from socialhood.errors import ApiError
from socialhood.platforms.deps import deps_from
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.registry import adapter_for
from socialhood.schemas.stories import Story, StoryList, StoryMentionList
from socialhood.services import connections
from socialhood.services import story_mentions as service

router = APIRouter(prefix="/v1/w/{wid}", tags=["stories"])

STORY_LIFETIME = timedelta(hours=24)
STORIES_FAILED = "Instagram didn't return your stories. Try again in a moment."


@router.get("/stories", operation_id="list_stories")
async def list_stories(
    request: Request,
    ctx: Admin,
    session: Session,
    account_id: Annotated[uuid.UUID, Query()],
) -> StoryList:
    """The account's live stories (the last 24 hours), newest first, for the story picker.
    An account with no stories (WhatsApp) gets an empty list; 502 platform_error when Instagram
    can't be reached."""
    acct = await connections.get_or_404(session, account_id)
    deps = deps_from(request.app.state.http, request.app.state.settings)
    try:
        found = await adapter_for(acct, deps).list_stories(acct)
    except PlatformError as error:
        raise ApiError("platform_error", STORIES_FAILED) from error
    now = datetime.now(UTC)
    return StoryList(
        items=[
            Story(
                id=s.platform_media_id,
                thumbnail_url=s.thumbnail_url,
                media_url=s.media_url,
                permalink=s.permalink,
                posted_at=s.posted_at,
                expires_at=s.posted_at + STORY_LIFETIME,
            )
            for s in found
            if s.posted_at + STORY_LIFETIME > now
        ]
    )


@router.get("/story-mentions", operation_id="list_story_mentions")
async def list_story_mentions(
    ctx: AnyMember,
    session: Session,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> StoryMentionList:
    """Who mentioned the account in their story, newest first. ``link_url`` is Instagram's address
    of the story and is only given while the story is live (until ``link_expires_at``);
    ``total_7d`` counts the last 7 days."""
    return await service.list_mentions(
        session, account_id=account_id, cursor=cursor, limit=limit, now=datetime.now(UTC)
    )
