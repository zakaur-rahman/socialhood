"""Stories and story mentions (GR-06, GR-07): the account's live stories for the editor's story
picker, and the Mentions list."""

from __future__ import annotations

import uuid
from datetime import datetime

from socialhood.schemas.common import ResponseModel


class Story(ResponseModel):
    """One of the account's live stories, as Instagram lists it. ``id`` is what a story reply
    automation is scoped to. ``expires_at`` is 24 hours after it was posted."""

    id: str
    thumbnail_url: str | None = None
    media_url: str | None = None
    permalink: str | None = None
    posted_at: datetime
    expires_at: datetime


class StoryList(ResponseModel):
    items: list[Story]


class MentionContact(ResponseModel):
    id: uuid.UUID
    display_name: str | None = None
    username: str | None = None
    profile_picture_url: str | None = None


class StoryMention(ResponseModel):
    """Someone mentioned the account in their story. ``link_url`` is Instagram's address of the
    story and is only given while the story is live (until ``link_expires_at``)."""

    id: uuid.UUID
    social_account_id: uuid.UUID
    mentioned_at: datetime
    contact: MentionContact | None = None
    conversation_id: uuid.UUID | None = None
    link_url: str | None = None
    link_expires_at: datetime | None = None


class StoryMentionList(ResponseModel):
    items: list[StoryMention]
    next_cursor: str | None = None
    total_7d: int  # mentions in the last 7 days, across the filtered accounts
