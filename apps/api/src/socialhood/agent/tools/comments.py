"""Comment tools (FR-AGT-02, FR-AGT-03, FR-AGT-06, TA.4; agent-architecture.html §5).

R1:
- get_post_comments(post, sentiment, intents, spam, topic, replied, range): read; the comments
  service (P6) with its analyses (TR-AI-11), on one post or across posts in a range (default the
  last 30 days). Unanalysed comments are counted, not guessed (FR-AGT-06).
- search_comments(q, range): read; comments whose text contains the words (default the last 90
  days).
- prepare_comment_reply(comment_id, text, private): draft; an action card that opens the post
  detail's reply box on that comment (FR-CMT-04), private replies only within 7 days of the
  comment and once per comment (the rules of services/comments/actions.py, checked here so the
  card never offers what the reply box would refuse).

Any member (``min_role`` agent), as on the Comments page.

R2: reply_to_comment (low), reply_to_comments (high, bulk, capped by bulk_max) and hide_comment
(low); capability send_replies (bulk_actions for many), through the comment actions.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from socialhood.agent.registry import DraftResult, ToolContext, ToolResult
from socialhood.agent.tools.common import (
    Period,
    clip,
    find_account,
    handle,
    limit_field,
    period,
    post_ref,
    quoted,
    ref,
    tool,
    when,
)
from socialhood.errors import ApiError, FieldError
from socialhood.models.agent import RiskTier
from socialhood.platforms.capabilities import Capability
from socialhood.repositories import comments as comments_repo
from socialhood.repositories import social_accounts
from socialhood.repositories.comments import CommentRow
from socialhood.schemas.agent import AnswerRef, CommentReplyAction, CommentReplyPrefill
from socialhood.schemas.inbox import IntentName
from socialhood.schemas.posts import SentimentName
from socialhood.services.analytics.common import capabilities_from
from socialhood.services.comments import actions
from socialhood.services.comments.queries import (
    CommentQuery,
    FoundComments,
    find_comments,
    post_or_404,
)

SpamName = Literal["exclude", "only", "include"]
SPAM: dict[str, bool | None] = {"exclude": False, "only": True, "include": None}
PRIVATE_REPLY_BYTES = 1000  # Instagram's limit (schemas/posts.PrivateReplyCreate)


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CommentItem(BaseModel):
    id: uuid.UUID
    post_id: uuid.UUID
    author: str | None = None  # @username
    text: str | None = None
    commented_at: datetime
    commented_at_label: str | None = None
    likes: int
    hidden: bool
    analysis: Literal["pending", "done", "skipped"]
    sentiment: str | None = None
    intent: str | None = None
    topic: str | None = None
    spam: bool | None = None
    replied: bool  # the account replied publicly or privately


class CommentsResult(ToolResult):
    post_id: uuid.UUID | None = None
    period: Period | None = None
    items: list[CommentItem]
    total: int  # comments matching the filters
    more: int
    in_scope: int  # comments on the post or in the range, before the analysis filters
    analysed: int  # of those, analysed (spam included)
    pending: int  # of those, still being analysed
    skipped: int  # of those, not analysed


def _item(ctx: ToolContext, row: CommentRow) -> CommentItem:
    c, a = row.comment, row.analysis
    done = c.analysis_status == "done" and a is not None
    return CommentItem(
        id=c.id,
        post_id=c.media_item_id,
        author=f"@{c.author_username}" if c.author_username else None,
        text=clip(c.text, 240),
        commented_at=c.commented_at,
        commented_at_label=when(ctx, c.commented_at),
        likes=c.like_count,
        hidden=c.hidden,
        analysis="done" if done else ("skipped" if c.analysis_status == "skipped" else "pending"),
        sentiment=a.sentiment if done and a else None,
        intent=a.intent if done and a else None,
        topic=a.topic if done and a else None,
        spam=a.is_spam if done and a else None,
        replied=bool(c.our_replied_at or c.private_reply_message_id),
    )


def _analysis_caveats(found: FoundComments, *, filtered: bool) -> list[str]:
    """What the counts leave out (FR-AGT-06): comments not analysed are never guessed."""
    caveats = []
    if found.pending:
        caveats.append(
            f"{found.pending} of {found.in_scope} comments are still being analysed"
            + (", so they aren't in these results." if filtered else ".")
        )
    if found.skipped:
        caveats.append(
            f"{found.skipped} comments weren't analysed (AI analysis off, credits used up or "
            "beyond the plan's posts)" + (", so they aren't in these results." if filtered else ".")
        )
    return caveats


def _result(
    ctx: ToolContext,
    found: FoundComments,
    *,
    summary: str,
    filtered: bool,
    post_refs: list[AnswerRef],
    span: Period | None,
    post_id: uuid.UUID | None,
) -> CommentsResult:
    items = [_item(ctx, row) for row in found.rows]
    return CommentsResult(
        summary=clip(summary, 300) or "Read comments",
        post_id=post_id,
        period=span,
        items=items,
        total=found.total,
        more=max(found.total - len(items), 0),
        in_scope=found.in_scope,
        analysed=found.in_scope - found.pending - found.skipped,
        pending=found.pending,
        skipped=found.skipped,
        refs=[*post_refs, *(ref("comment", i.id, quoted(i.text), i.post_id) for i in items)],
        caveats=_analysis_caveats(found, filtered=filtered),
    )


# ---------------------------------------------------------------- get_post_comments


class GetPostCommentsInput(_Input):
    post_id: uuid.UUID | None = Field(
        default=None, description="One post; omitted: comments on every post in the range."
    )
    sentiment: SentimentName | None = None
    intents: list[IntentName] = Field(
        default_factory=list,
        max_length=6,
        description=(
            "Comment intents, e.g. pricing and product_inquiry for questions, purchase for buying."
        ),
    )
    topic: str | None = Field(
        default=None, max_length=40, description="Words in the analysed topic, e.g. “price”."
    )
    spam: SpamName = Field(default="exclude", description="exclude (default), only or include.")
    replied: bool | None = Field(
        default=None, description="true: only comments you replied to; false: not replied yet."
    )
    range: str | None = Field(
        default=None,
        max_length=80,
        description="When the comments were made, e.g. “last week”. Without a post: default "
        "the last 30 days.",
    )
    account: str | None = Field(default=None, max_length=100)
    limit: int = limit_field()


@tool(
    name="get_post_comments",
    label="Reading comments",
    description=(
        "Comments on one post, or across posts in a period, filtered by sentiment, intents, "
        "topic, spam and whether you replied; newest first, with how many match and how many "
        "aren't analysed yet."
    ),
    input_model=GetPostCommentsInput,
    result_model=CommentsResult,
)
async def get_post_comments(ctx: ToolContext, args: GetPostCommentsInput) -> CommentsResult:
    post_refs = []
    if args.post_id is not None:
        post = await post_or_404(ctx.session, args.post_id)
        post_refs.append(post_ref(post, ctx))
    span = period(ctx, args.range, default=None if args.post_id else "the last 30 days")
    acct = await find_account(ctx, args.account)
    query = CommentQuery(
        post_id=args.post_id,
        account_id=acct.id if acct else None,
        start=span.start if span else None,
        end=span.end if span else None,
        sentiment=args.sentiment,
        intents=tuple(args.intents),
        topic=args.topic,
        spam=SPAM[args.spam],
        replied=args.replied,
    )
    found = await find_comments(ctx.session, query, limit=args.limit)
    words = [w for w in (args.sentiment, "spam" if args.spam == "only" else None) if w]
    what = " ".join([*words, "comment" if found.total == 1 else "comments"])
    where = f" on the {post_refs[0].label}" if post_refs else ""
    summary = f"Found {found.total} {what}{where}"
    if args.topic:
        summary += f" about “{clip(args.topic, 30)}”"
    if span:
        summary += f", {span.label}"
    filtered = bool(args.sentiment or args.intents or args.topic or args.spam == "only")
    return _result(
        ctx,
        found,
        summary=summary,
        filtered=filtered,
        post_refs=post_refs,
        span=Period.of(span) if span else None,
        post_id=args.post_id,
    )


# ---------------------------------------------------------------- search_comments


class SearchCommentsInput(_Input):
    q: str = Field(min_length=1, max_length=100, description="Words the comment contains.")
    range: str | None = Field(
        default=None, max_length=80, description="When, e.g. “this month”; default 90 days."
    )
    post_id: uuid.UUID | None = None
    sentiment: SentimentName | None = None
    limit: int = limit_field()


@tool(
    name="search_comments",
    label="Searching comments",
    description="Comments whose text contains the words, newest first (default: last 90 days).",
    input_model=SearchCommentsInput,
    result_model=CommentsResult,
)
async def search_comments(ctx: ToolContext, args: SearchCommentsInput) -> CommentsResult:
    post_refs = []
    if args.post_id is not None:
        post_refs.append(post_ref(await post_or_404(ctx.session, args.post_id), ctx))
    span = period(ctx, args.range, default="the last 90 days")
    query = CommentQuery(
        post_id=args.post_id,
        start=span.start if span else None,
        end=span.end if span else None,
        q=args.q,
        sentiment=args.sentiment,
        spam=None,
    )
    found = await find_comments(ctx.session, query, limit=args.limit)
    noun = "comment" if found.total == 1 else "comments"
    summary = f"Found {found.total} {noun} mentioning “{clip(args.q, 40)}”"
    if span:
        summary += f", {span.label}"
    return _result(
        ctx,
        found,
        summary=summary,
        filtered=args.sentiment is not None,
        post_refs=post_refs,
        span=Period.of(span) if span else None,
        post_id=args.post_id,
    )


# ---------------------------------------------------------------- prepare_comment_reply


class PrepareCommentReplyInput(_Input):
    comment_id: uuid.UUID
    text: str = Field(min_length=1, max_length=2200, description="The reply, as it will be sent.")
    private: bool = Field(
        default=False,
        description="A private reply (a DM to the commenter) instead of a public reply.",
    )


class PrepareCommentReplyResult(DraftResult):
    comment_id: uuid.UUID
    post_id: uuid.UUID
    private: bool
    comment_text: str | None = None
    author: str | None = None
    private_reply_until: datetime | None = None  # Instagram's 7 days after the comment


def _refuse(message: str) -> ApiError:
    return ApiError("conflict", message)


@tool(
    name="prepare_comment_reply",
    label="Preparing a reply to the comment",
    description=(
        "Prepare a public reply (or a private reply, a DM) to one comment: returns a card that "
        "opens the post's reply box with the text filled in. Sends nothing. Private replies are "
        "allowed once per comment, within 7 days of it."
    ),
    input_model=PrepareCommentReplyInput,
    result_model=PrepareCommentReplyResult,
    tier=RiskTier.DRAFT,
)
async def prepare_comment_reply(
    ctx: ToolContext, args: PrepareCommentReplyInput
) -> PrepareCommentReplyResult:
    comment = await comments_repo.get(ctx.session, args.comment_id)
    if comment is None:
        raise ApiError("not_found", "That comment wasn't found.")
    if comment.deleted_at is not None:
        raise _refuse(actions.DELETED)
    post = await post_or_404(ctx.session, comment.media_item_id)
    acct = await social_accounts.get(ctx.session, comment.social_account_id)
    needs = Capability.PRIVATE_REPLY if args.private else Capability.COMMENTS
    if acct is None or needs not in capabilities_from(ctx.platform)(acct):
        who = handle(acct) if acct else "This account"
        raise ApiError("capability_unavailable", f"{who} can't reply to comments from here.")
    caveats: list[str] = []
    deadline = comment.commented_at + actions.PRIVATE_REPLY_LIMIT
    if args.private:
        if len(args.text.encode()) > PRIVATE_REPLY_BYTES:
            raise ApiError(
                "validation_error",
                "A private reply can be at most 1,000 bytes.",
                errors=[FieldError("text", "Shorten the private reply.")],
            )
        if comment.private_reply_message_id is not None:
            raise _refuse(actions.ONE_PER_COMMENT)
        if deadline <= ctx.now:
            raise _refuse(actions.TOO_OLD)
        if not comment.author_platform_user_id:
            raise _refuse(actions.NO_COMMENTER)
        if await comments_repo.automation_reply_queued(ctx.session, comment.id):
            raise _refuse(actions.AUTOMATION_QUEUED)
        note = f"Instagram allows one private reply per comment, until {when(ctx, deadline)}."
    else:
        note = "Nothing is posted until you send it."
        if comment.our_reply_text:
            caveats.append(f"You already replied publicly: {quoted(comment.our_reply_text)}.")
    kind = "private" if args.private else "public"
    author = f"@{comment.author_username}" if comment.author_username else None
    return PrepareCommentReplyResult(
        summary=clip(f"Prepared a {kind} reply to {author or 'the comment'}", 300)
        or "Prepared a reply",
        comment_id=comment.id,
        post_id=post.id,
        private=args.private,
        comment_text=clip(comment.text, 240),
        author=author,
        private_reply_until=deadline if args.private else None,
        refs=[ref("comment", comment.id, quoted(comment.text), post.id), post_ref(post, ctx)],
        caveats=caveats,
        action_card=CommentReplyAction(
            kind="reply_to_comment",
            label="Send a private reply" if args.private else "Reply to this comment",
            route=f"comments/{post.id}?comment={comment.id}&reply={kind}",
            note=clip(note, 200),
            prefill=CommentReplyPrefill(
                comment_id=comment.id, post_id=post.id, text=args.text, private=args.private
            ),
        ),
    )
