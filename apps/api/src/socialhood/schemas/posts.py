"""Posts and comments (§2.15; FR-CMT-03, FR-CMT-04, UX-SCR-05): the Comments grid, post detail,
the comment list and comment actions.

The P6 contract. ``post.updated`` carries a ``PostDetail`` and ``comment.created`` /
``comment.updated`` carry a ``Comment`` (TR-RT-03), so the web patches its caches from events.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel
from socialhood.schemas.inbox import IntentName

SentimentName = Literal["positive", "neutral", "negative"]
CommentAnalysisStatus = Literal["pending", "done", "skipped"]

# The post detail's filter chips (UX-SCR-05). Every filter leaves out deleted comments.
# - all: every comment, hidden ones included (shown as hidden)
# - positive, neutral, negative: analysed, not spam, with that sentiment
# - questions, buying: analysed, not spam, intent in COMMENT_FILTER_INTENTS
# - spam: analysed as spam; hidden: hidden on Instagram (by a member or auto-hide, FR-CMT-05)
CommentFilter = Literal[
    "all", "positive", "neutral", "negative", "questions", "buying", "spam", "hidden"
]
COMMENT_FILTER_INTENTS: dict[str, tuple[IntentName, ...]] = {
    "questions": ("pricing", "product_inquiry", "shipping", "order_status", "support"),
    "buying": ("purchase", "pricing"),
}


# ---- posts


class CommentStats(ResponseModel):
    """A post's comment counts (``media_items.comment_stats``): ``total`` grows as comments arrive,
    the rest are recounted by the analysis job.

    ``positive + neutral + negative`` counts analysed comments that are not spam; ``spam`` counts
    analysed spam. ``analysed`` counts every comment no longer waiting: analysed, or skipped (AI
    analysis off, AI credits used up, beyond the plan's posts, empty), so while ``analysed <
    total`` the page shows "Analysing {analysed} of {total} comments" (FR-CMT-02) and the progress
    always ends. Deleted comments are not counted.
    """

    total: int
    analysed: int
    positive: int
    neutral: int
    negative: int
    spam: int

    @classmethod
    def from_stored(cls, raw: Mapping[str, Any] | None) -> CommentStats:
        """The stored JSON, with missing counts as 0 (posts not analysed yet store {})."""
        raw = raw or {}
        return cls(**{name: int(raw.get(name) or 0) for name in cls.model_fields})


class PostSummary(ResponseModel):
    """A synced post: the automation post picker (P4) and the Comments grid (FR-CMT-03)."""

    id: uuid.UUID
    social_account_id: uuid.UUID
    platform_media_id: str
    media_type: str
    caption: str | None = None
    media_url: str | None = None
    thumbnail_url: str | None = None
    permalink: str | None = None
    posted_at: datetime
    like_count: int | None = None  # from Instagram at the last sync or snapshot
    comments_count: int | None = None
    stats: CommentStats


class PostList(ResponseModel):
    items: list[PostSummary]
    next_cursor: str | None = None


class PostTopic(ResponseModel):
    """One of a post's topic labels (TR-AI-11): the model merges the most frequent comment topics
    into at most 6 labels; code counts each label's comments and their sentiment."""

    label: str
    count: int
    positive: int
    neutral: int
    negative: int


class PostDetail(PostSummary):
    """GET …/posts/{post_id} (FR-CMT-04): the post, its counts and sentiment split (``stats``),
    the summary of two or three sentences and the topics, largest first."""

    summary: str | None = None  # None until summarize_post first runs
    summary_updated_at: datetime | None = None
    topics: list[PostTopic]  # at most 6


# ---- comments


class CommentAnalysis(ResponseModel):
    """analyze_comments' reading of one comment (TR-AI-11)."""

    sentiment: SentimentName
    sentiment_score: float  # -1 to 1
    intent: IntentName
    is_spam: bool
    topic: str | None = None  # at most 3 words, lowercase


class CommentPublicReply(ResponseModel):
    """The account's public reply under the comment (a member's or an automation's)."""

    text: str
    platform_id: str | None = None
    replied_at: datetime


class CommentPrivateReply(ResponseModel):
    """The one private reply Instagram allows per comment: a DM in the commenter's
    conversation."""

    message_id: uuid.UUID
    conversation_id: uuid.UUID


class Comment(ResponseModel):
    """A comment row (UX-SCR-05). Replies to other comments carry the parent's platform id."""

    id: uuid.UUID
    post_id: uuid.UUID  # media_items.id
    social_account_id: uuid.UUID
    contact_id: uuid.UUID | None = None
    platform_comment_id: str
    parent_platform_comment_id: str | None = None
    author_username: str | None = None
    author_profile_picture_url: str | None = None  # the contact's, when known
    text: str
    like_count: int
    hidden: bool
    commented_at: datetime
    deleted_at: datetime | None = None  # only in the comment.updated of a delete: drop the row
    analysis_status: CommentAnalysisStatus
    analysis: CommentAnalysis | None = None  # None while pending or when skipped
    public_reply: CommentPublicReply | None = None
    private_reply: CommentPrivateReply | None = None


class CommentList(ResponseModel):
    """Newest first."""

    items: list[Comment]
    next_cursor: str | None = None


class CommentReplyCreate(RequestModel):
    """POST …/comments/{comment_id}/reply: a public reply under the comment."""

    text: str = Field(min_length=1, max_length=2200)


class PrivateReplyCreate(RequestModel):
    """POST …/comments/{comment_id}/private-reply: a DM to the commenter, text only (Instagram's
    private replies carry no attachments). Instagram's limit is 1,000 bytes; the service checks
    bytes."""

    text: str = Field(min_length=1, max_length=1000)
