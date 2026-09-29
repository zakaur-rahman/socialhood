"""The agent eval's requests (TA.6; agent-architecture.html §18): natural questions a bakery owner
or a team member asks Ask Social Hood, in English, Hindi and Hinglish, over the seeded workspace
(tests/evals/seed.py).

Each case lists the tools that can answer it (``expect_tools``: at least one must be called) and
tools it must not use (``forbid_tools``). ``expect_numbers`` are computed from the seed's
declarations by the functions in seed.py, never typed in; ``alternatives`` cover a second fair
reading of the question (with or without spam, same format or all posts). ``expect_text`` holds
what an honest answer must say (a caveat, "none", a refusal), as case-insensitive regexes;
``expect_card`` the action card a draft request must produce; ``role`` the member who asks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from tests.evals import seed as S
from tests.evals.checks import Expect

Role = Literal["owner", "admin", "agent"]
Lang = Literal["en", "hi", "hinglish"]


@dataclass(frozen=True)
class Case:
    id: str
    request: str
    expect_tools: frozenset[str]
    forbid_tools: frozenset[str] = frozenset()
    expect_numbers: tuple[Expect, ...] = ()
    expect_card: str | None = None
    expect_text: tuple[str, ...] = ()
    role: Role = "owner"
    lang: Lang = "en"
    area: str = ""


def tools(*names: str) -> frozenset[str]:
    return frozenset(names)


def e(value: float | None, *alternatives: float, label: str = "") -> Expect:
    assert value is not None, f"the seed has no value for {label or 'this case'}"
    return Expect(float(value), tuple(float(a) for a in alternatives), label)


# What an honest answer says when there's nothing, when a member can't see an area, when data
# isn't available.
NONE = (
    r"\bno\b|\bnone\b|nobody|no one|didn't find|couldn't find|not find|haven't|there are 0"
    r"|\b0\b|koi nahi|कोई नहीं|nahi"
)
ADMIN_ONLY = (
    r"admin|owner|access|permission|can't|cannot|not able|unable|don't have|isn't available"
    r"|not available"
)
NO_INSIGHTS = r"insight|not granted|not available|isn't available|aren't available|unavailable"
FACEBOOK = r"facebook"
NOT_CONNECTED = (
    r"not connected|isn't connected|aren't connected|later release|not available"
    r"|not supported|isn't supported"
)

# ---------------------------------------------------------------- the seed's figures

P1 = S.POST["p1"]
P2 = S.POST["p2"]
LW = S.last_week()
TW = S.this_week()
TM = S.this_month()
LM = S.last_month()
L30 = S.last_days(30)

NEEDS_REPLY = len(S.conversations("needs_reply"))
LEADS = S.conversations("leads")
TODAY_START = S.day_start(S.TODAY)
MONDAY_START = S.day_start(TW[0])


def _comments_in(span: tuple[S.date, S.date], **kw: object) -> int:
    start, end = S.days(*span)
    return len(S.comments(start=start, end=end, **kw))  # type: ignore[arg-type]


P1_24H = S.metrics_at(P1, "24h")
P2_72H = S.metrics_at(P2, "72h")
TOP_REACH_TM, _ = S.top_posts("reach", *TM, n=3)
TOP_LIKES_30, _ = S.top_posts("likes", *L30, n=5)
TOP_ER_LM, _ = S.top_posts("engagement_rate", *LM, n=1)
TOP_REACH_30, _ = S.top_posts("reach", *L30, n=1)
TOP_SAVES_TM, _ = S.top_posts("saves", *TM, n=1)
SPLIT_P1 = S.sentiment_split(post="p1")
SPLIT_TM = S.sentiment_split(since=TM[0], until=TM[1])
SPLIT_LW = S.sentiment_split(since=LW[0], until=LW[1])
TOPICS_TM = S.topic_counts(since=TM[0], until=TM[1])
REACH_SAME = S.compare(P1, "reach")
REACH_ALL = S.compare(P1, "reach", same_format=False)
MENU_7 = S.automation_figures("menu", 7)
PRICE_30 = S.automation_figures("price", 30)

CASES: tuple[Case, ...] = (
    # ------------------------------------------------------------ inbox
    Case(
        "inbox-needs-reply",
        "How many conversations are waiting for a reply?",
        tools("search_conversations"),
        expect_numbers=(e(NEEDS_REPLY, label="needs reply"),),
        area="inbox",
    ),
    Case(
        "inbox-needs-reply-hinglish",
        "Kitne customers ko abhi reply karna baaki hai?",
        tools("search_conversations"),
        expect_numbers=(e(NEEDS_REPLY, label="needs reply"),),
        lang="hinglish",
        area="inbox",
    ),
    Case(
        "inbox-needs-reply-hindi",
        "किन ग्राहकों को अभी जवाब देना बाकी है?",
        tools("search_conversations"),
        lang="hi",
        area="inbox",
    ),
    Case(
        "inbox-leads-count",
        "How many leads do I have right now?",
        tools("search_conversations"),
        expect_numbers=(e(len(LEADS), label="leads"),),
        area="inbox",
    ),
    Case(
        "inbox-leads-scores",
        "List my leads with their lead scores.",
        tools("search_conversations"),
        expect_numbers=tuple(e(c.lead_score, label=f"{c.name}'s score") for c in LEADS),
        area="inbox",
    ),
    Case(
        "inbox-today",
        "How many conversations had activity today?",
        tools("search_conversations"),
        expect_numbers=(e(len(S.conversations(start=TODAY_START)), label="active today"),),
        area="inbox",
    ),
    Case(
        "inbox-archived",
        "How many conversations have I archived?",
        tools("search_conversations"),
        expect_numbers=(e(len(S.conversations("archived")), label="archived"),),
        area="inbox",
    ),
    Case(
        "inbox-whatsapp",
        "How many WhatsApp conversations are open?",
        tools("search_conversations"),
        expect_numbers=(e(len(S.conversations(platform="whatsapp")), label="whatsapp"),),
        area="inbox",
    ),
    Case(
        "inbox-closing",
        "Whose reply window is about to close?",
        tools("search_conversations"),
        expect_text=(r"Rahul",),
        area="inbox",
    ),
    Case(
        "inbox-refund",
        "Did any customer ask for a refund?",
        tools("search_conversations", "get_conversation"),
        expect_text=(r"Rahul",),
        area="inbox",
    ),
    Case(
        "inbox-rahul-said",
        "What exactly did Rahul say about his order?",
        tools("get_conversation"),
        expect_text=(r"damaged",),
        area="inbox",
    ),
    Case(
        "inbox-summary-priya",
        "Summarise my conversation with Priya Shah.",
        tools("get_conversation"),
        expect_text=(r"Baner",),
        area="inbox",
    ),
    Case(
        "inbox-rahul-mood",
        "Is Rahul Mehta happy or upset with us?",
        tools("get_conversation", "get_customer", "search_conversations", "find_contact"),
        expect_text=(r"upset|unhappy|negative|disappoint|frustrat|angry",),
        area="inbox",
    ),
    Case(
        "inbox-priya-ambiguous",
        "What did Priya ask about?",
        tools("find_contact", "search_conversations", "get_conversation"),
        expect_text=(r"Priya Shah.*Priya Nair|Priya Nair.*Priya Shah|which Priya|which one",),
        area="inbox",
    ),
    Case(
        "inbox-find-meera",
        "Find the customer called Meera.",
        tools("find_contact", "search_conversations"),
        expect_text=(r"WhatsApp",),
        area="inbox",
    ),
    Case(
        "inbox-last-week",
        "How many conversations were last active last week?",
        tools("search_conversations"),
        expect_numbers=(e(len(S.conversations(start=S.days(*LW)[0], end=S.days(*LW)[1]))),),
        area="inbox",
    ),
    Case(
        "inbox-since-monday",
        "How many open conversations have had messages since Monday?",
        tools("search_conversations"),
        expect_numbers=(e(len(S.conversations(start=MONDAY_START)), label="since Monday"),),
        area="inbox",
    ),
    Case(
        "inbox-sneha-sentiment",
        "What's the sentiment of Sneha's latest message?",
        tools("get_conversation", "get_customer"),
        expect_text=(
            r"not (been |yet )?analy[sz]|no analysis|hasn't been analy|isn't analy|not yet",
        ),
        area="inbox",
    ),
    Case(
        "inbox-facebook",
        "Any new messages from Facebook?",
        tools("search_conversations"),
        expect_text=(FACEBOOK, NOT_CONNECTED),
        area="inbox",
    ),
    Case(
        "inbox-wedding",
        "Did anyone message us about wedding cakes?",
        tools("search_conversations"),
        expect_text=(NONE,),
        area="inbox",
    ),
    Case(
        "inbox-upset-hinglish",
        "Koi customer naraz hai kya?",
        # Upset customers are in the inbox (Rahul) and in the comments (price, delivery): either
        # reading answers the question.
        tools(
            "search_conversations",
            "get_conversation",
            "get_post_comments",
            "comment_topics",
            "sentiment_distribution",
        ),
        expect_text=(r"Rahul|राहुल|price|expensive|delivery|mehng|महंग",),
        lang="hinglish",
        area="inbox",
    ),
    Case(
        "inbox-rahul-hinglish",
        "Rahul ne apne order ke baare mein kya bola?",
        tools("get_conversation"),
        expect_text=(r"damage|kharab|toot|टूट|खराब|refund|रिफंड",),
        lang="hinglish",
        area="inbox",
    ),
    Case(
        "inbox-leads-hinglish",
        "Mere hot leads kaun kaun hain?",
        tools("search_conversations"),
        expect_text=(r"Meera|मीरा",),
        lang="hinglish",
        area="inbox",
    ),
    Case(
        "inbox-yesterday-kal",
        "Kal kin customers ne message kiya tha?",
        tools("search_conversations"),
        lang="hinglish",
        area="inbox",
    ),
    Case(
        "customer-neha-comments",
        "Has @neha.bakes commented on my posts? How many times?",
        tools("get_customer"),
        expect_numbers=(
            e(len([c for c in (S.COMMENT[k][1] for k in S.COMMENT) if c.author == "neha.bakes"])),
        ),
        area="inbox",
    ),
    Case(
        "customer-ananya-score",
        "What's Ananya Gupta's lead score?",
        tools("get_customer", "get_conversation", "search_conversations", "find_contact"),
        expect_numbers=(e(S.CONVERSATION["ananya"].lead_score, label="lead score"),),
        area="inbox",
    ),
    # ------------------------------------------------------------ drafts
    Case(
        "draft-priya",
        "Draft a reply to Priya Shah saying yes, we deliver to Baner.",
        tools("draft_reply"),
        expect_card="schedule_message",
        area="drafts",
    ),
    Case(
        "draft-rahul",
        "Draft an apology to Rahul for the damaged order and offer a replacement.",
        tools("draft_reply"),
        expect_card="schedule_message",
        area="drafts",
    ),
    Case(
        "draft-sneha-closed",
        "Draft a reply to Sneha Kulkarni about the eggless option.",
        tools("draft_reply", "get_conversation", "find_contact", "search_conversations"),
        expect_text=(r"window|24 hours|24-hour|closed",),
        area="drafts",
    ),
    Case(
        "sched-rohan",
        "Schedule a message to Rohan for tomorrow at 9 AM saying we'll share Dubai shipping "
        "details.",
        tools("prepare_scheduled_message"),
        expect_card="schedule_message",
        area="drafts",
    ),
    Case(
        "sched-meera-late",
        "Schedule a message to Meera Iyer for tomorrow at 10 AM: your cupcakes are confirmed.",
        tools("prepare_scheduled_message"),
        expect_card="schedule_message",
        expect_text=(r"window",),
        area="drafts",
    ),
    Case(
        "sched-ananya-hinglish",
        "Ananya ko kal shaam 6 baje message schedule kar do ki unka cake ready hai.",
        tools("prepare_scheduled_message"),
        expect_card="schedule_message",
        expect_text=(r"window|विंडो|closes|band",),
        lang="hinglish",
        area="drafts",
    ),
    Case(
        "sched-karan-closed",
        "Schedule a thank-you message to Karan Singh for tomorrow at 11 AM.",
        tools("prepare_scheduled_message"),
        expect_text=(r"window|closed|can't|cannot",),
        area="drafts",
    ),
    Case(
        "sched-priya-ambiguous",
        "Schedule a message to Priya for 5 PM today saying her order is ready.",
        tools("prepare_scheduled_message", "find_contact", "search_conversations"),
        expect_text=(r"which|Priya Shah.*Priya Nair|Priya Nair.*Priya Shah",),
        area="drafts",
    ),
    # ------------------------------------------------------------ comments
    Case(
        "cmt-latest-negative",
        "Show me the negative comments on my latest post.",
        tools("get_post_comments", "sentiment_distribution"),
        expect_numbers=(e(len(S.comments(post="p1", sentiment="negative")), label="negative"),),
        area="comments",
    ),
    Case(
        "cmt-lastweek-negative-hinglish",
        "Pichle hafte kitne negative comments aaye?",
        tools("get_post_comments", "sentiment_distribution"),
        expect_numbers=(e(_comments_in(LW, sentiment="negative"), label="negative last week"),),
        lang="hinglish",
        area="comments",
    ),
    Case(
        "cmt-price-question",
        "Which comments are asking about the price?",
        tools("get_post_comments", "search_comments", "comment_topics"),
        area="comments",
    ),
    Case(
        "cmt-spam-month",
        "How many spam comments did I get this month?",
        tools("get_post_comments", "sentiment_distribution"),
        expect_numbers=(e(_comments_in(TM, spam=True), label="spam this month"),),
        area="comments",
    ),
    Case(
        "cmt-unreplied-latest",
        "Which comments on my latest reel haven't been replied to yet?",
        tools("get_post_comments"),
        expect_numbers=(
            e(
                len(S.comments(post="p1", replied=False)),
                len(S.comments(post="p1", replied=False, spam=None)),
                label="not replied",
            ),
        ),
        area="comments",
    ),
    Case(
        "cmt-search-eggless",
        "Find comments that mention eggless.",
        tools("search_comments"),
        expect_numbers=(e(len(S.comments(q="eggless", spam=None)), label="eggless"),),
        area="comments",
    ),
    Case(
        "cmt-search-pineapple",
        "Any comments mentioning pineapple?",
        tools("search_comments"),
        expect_text=(NONE,),
        area="comments",
    ),
    Case(
        "cmt-yesterday-kal",
        "Kal kitne comments aaye the?",
        tools("get_post_comments", "sentiment_distribution"),
        expect_numbers=(
            e(
                _comments_in((S.TODAY - timedelta(days=1),) * 2, spam=None),
                _comments_in((S.TODAY - timedelta(days=1),) * 2),
                label="yesterday",
            ),
        ),
        lang="hinglish",
        area="comments",
    ),
    Case(
        "cmt-today-hindi",
        "आज कितने कमेंट आए?",
        tools("get_post_comments", "sentiment_distribution"),
        expect_numbers=(
            e(
                _comments_in((S.TODAY, S.TODAY), spam=None),
                _comments_in((S.TODAY, S.TODAY)),
                label="today",
            ),
        ),
        lang="hi",
        area="comments",
    ),
    Case(
        "cmt-replied-month",
        "How many comments have we replied to this month?",
        tools("get_post_comments"),
        expect_numbers=(e(_comments_in(TM, replied=True, spam=None), label="replied"),),
        area="comments",
    ),
    Case(
        "cmt-pending-latest",
        "Have all the comments on my latest post been analysed?",
        tools("get_post_comments", "sentiment_distribution", "get_latest_post"),
        expect_numbers=(e(SPLIT_P1.total - SPLIT_P1.analysed, label="not analysed"),),
        expect_text=(r"analy",),
        area="comments",
    ),
    Case(
        "cmt-hampers-post",
        "What are people saying on my Diwali hampers post?",
        tools("comment_topics", "get_post_comments", "sentiment_distribution"),
        expect_text=(r"price|expensive",),
        area="comments",
    ),
    Case(
        "cmt-reply-eggless",
        "Reply to the comment asking about an eggless version with: Yes, all our cakes can be "
        "made eggless!",
        tools("prepare_comment_reply"),
        expect_card="reply_to_comment",
        area="comments",
    ),
    Case(
        "cmt-private-amit",
        "Send @amit.k a private reply on his comment on my latest reel saying we'll give him 10% "
        "off his next order.",
        tools("prepare_comment_reply"),
        expect_card="reply_to_comment",
        area="comments",
    ),
    Case(
        "cmt-private-kavya-old",
        "Send a private reply to @kavya.r's price question on the Diwali post.",
        tools("prepare_comment_reply", "search_comments", "get_post_comments"),
        expect_text=(r"7 days|seven days|too old|older than|can't|cannot|no longer",),
        area="comments",
    ),
    Case(
        "cmt-complaints-hinglish",
        "Comments mein log kis cheez ki shikayat kar rahe hain?",
        tools("comment_topics", "get_post_comments"),
        expect_text=(r"price|expensive|delivery|mehng|महंग|महँग|डिलीवरी|keemat|kimat|कीमत",),
        lang="hinglish",
        area="comments",
    ),
    Case(
        "cmt-week-vs-last",
        "Did I get more comments this week than last week?",
        tools("get_post_comments", "sentiment_distribution"),
        expect_numbers=(
            e(
                _comments_in((TW[0], S.TODAY), spam=None),
                _comments_in((TW[0], S.TODAY)),
                label="this week",
            ),
            e(_comments_in(LW, spam=None), _comments_in(LW), label="last week"),
        ),
        area="comments",
    ),
    Case(
        "cmt-priya-comment",
        "What did Priya Shah comment on my posts?",
        tools("get_customer"),
        expect_text=(r"Booked mine|Saturday",),
        area="comments",
    ),
    # ------------------------------------------------------------ posts
    Case(
        "post-latest",
        "What was my latest post?",
        tools("get_latest_post", "get_posts"),
        expect_text=(r"reel",),
        area="posts",
    ),
    Case(
        "post-latest-age",
        "How many hours ago did I publish my latest post?",
        tools("get_latest_post", "get_posts"),
        expect_numbers=(e(S.age_hours(P1), label="hours"),),
        area="posts",
    ),
    Case(
        "post-count-month",
        "How many posts did I publish this month?",
        tools("get_posts"),
        expect_numbers=(e(len(S.posts(start=S.days(*TM)[0])), label="posts this month"),),
        area="posts",
    ),
    Case(
        "post-reels-60",
        "How many reels have I posted in the last 60 days?",
        tools("get_posts"),
        expect_numbers=(
            e(len(S.posts(start=S.NOW - timedelta(days=60), media_format="reel")), label="reels"),
        ),
        area="posts",
    ),
    Case(
        "post-search-diwali",
        "Find my post about Diwali hampers.",
        tools("search_posts", "get_posts"),
        expect_text=(r"Diwali",),
        area="posts",
    ),
    Case(
        "post-search-pineapple",
        "Did I ever post about pineapple cake?",
        tools("search_posts"),
        expect_text=(NONE,),
        area="posts",
    ),
    Case(
        "post-maple-cakes",
        "What's the latest post on @maple.cakes?",
        tools("get_latest_post", "get_posts"),
        expect_text=(r"birthday",),
        area="posts",
    ),
    Case(
        "post-last-week",
        "How many posts did I put up last week?",
        tools("get_posts"),
        expect_numbers=(e(len(S.posts(start=S.days(*LW)[0], end=S.days(*LW)[1]))),),
        area="posts",
    ),
    Case(
        "post-this-week-hinglish",
        "Is hafte maine kitni posts daali?",
        tools("get_posts"),
        expect_numbers=(e(len(S.posts(start=MONDAY_START))),),
        lang="hinglish",
        area="posts",
    ),
    Case(
        "post-facebook",
        "How are my Facebook page posts doing?",
        tools("get_posts", "get_latest_post", "top_posts"),
        expect_text=(FACEBOOK, NOT_CONNECTED),
        area="posts",
    ),
    # ------------------------------------------------------------ analytics
    Case(
        "perf-latest-reach",
        "How many people did my latest reel reach?",
        tools("post_performance"),
        expect_numbers=(e(P1_24H["reach"], label="reach at 24 h"),),
        area="analytics",
    ),
    Case(
        "perf-latest-er",
        "What's the engagement rate of my latest post?",
        tools("post_performance"),
        expect_numbers=(e(S.engagement_rate(P1_24H), label="engagement rate"),),
        area="analytics",
    ),
    Case(
        "perf-cheesecake-72h",
        "How did the blueberry cheesecake post do after 72 hours? Give me reach and likes.",
        tools("post_performance"),
        expect_numbers=(e(P2_72H["reach"], label="reach"), e(P2_72H["likes"], label="likes")),
        area="analytics",
    ),
    Case(
        "perf-birthday-noinsights",
        "How many people did my birthday cakes post on @maple.cakes reach?",
        tools("post_performance", "get_posts", "get_latest_post", "search_posts"),
        expect_text=(NO_INSIGHTS,),
        area="analytics",
    ),
    Case(
        "perf-latest-7d",
        "What were my latest reel's numbers after 7 days?",
        tools("post_performance"),
        expect_text=(r"younger|hasn't reached|not.*7 days|too new|only|26 hours|24 hours|yet",),
        area="analytics",
    ),
    Case(
        "cmp-latest-10",
        "How did my latest post perform compared with my previous 10 posts?",
        tools("compare_posts"),
        expect_numbers=(e(REACH_SAME.diff_pct, *(n for n in [REACH_ALL.diff_pct] if n)),),
        area="analytics",
    ),
    Case(
        "cmp-hinglish",
        "Meri latest reel pichli reels se better perform kar rahi hai ya nahi?",
        tools("compare_posts"),
        expect_text=(r"better|zyada|above|higher|acch|achh|बेहतर|ज़्यादा|ज्यादा|more",),
        lang="hinglish",
        area="analytics",
    ),
    Case(
        "cmp-hampers-30d",
        "Compare my Diwali hampers post with my other posts from the last 30 days.",
        tools("compare_posts"),
        area="analytics",
    ),
    Case(
        "cmp-latest-24h",
        "Compare my latest reel at 24 hours with my previous reels at 24 hours.",
        tools("compare_posts"),
        expect_numbers=(
            e(REACH_SAME.diff_pct, label="reach vs median"),
            e(REACH_SAME.size, label="baseline size"),
        ),
        area="analytics",
    ),
    Case(
        "top-reach-month",
        "What were my top 3 posts by reach this month?",
        tools("top_posts"),
        expect_numbers=tuple(e(v, label=p.key) for p, v in TOP_REACH_TM),
        area="analytics",
    ),
    Case(
        "top-likes-30",
        "Show my top 5 posts by likes in the last 30 days.",
        tools("top_posts"),
        expect_numbers=tuple(e(v, label=p.key) for p, v in TOP_LIKES_30),
        area="analytics",
    ),
    Case(
        "top-er-last-month",
        "Which post had the best engagement rate last month?",
        tools("top_posts"),
        expect_numbers=(e(S.first(TOP_ER_LM), label="engagement rate"),),
        area="analytics",
    ),
    Case(
        "top-reach-hindi",
        "पिछले 30 दिनों में सबसे ज़्यादा reach वाली पोस्ट कौन सी थी?",
        tools("top_posts"),
        expect_numbers=(e(S.first(TOP_REACH_30), label="reach"),),
        lang="hi",
        area="analytics",
    ),
    Case(
        "top-saves",
        "Which post got the most saves this month?",
        tools("top_posts"),
        expect_numbers=(e(S.first(TOP_SAVES_TM), label="saves"),),
        area="analytics",
    ),
    Case(
        "top-maple-cakes",
        "Rank my @maple.cakes posts by reach.",
        tools("top_posts"),
        expect_text=(NO_INSIGHTS,),
        area="analytics",
    ),
    Case(
        "sent-latest",
        "What percentage of comments on my latest post are positive?",
        tools("sentiment_distribution"),
        expect_numbers=(e(SPLIT_P1.pct("positive"), label="positive %"),),
        expect_text=(r"analy",),
        area="analytics",
    ),
    Case(
        "sent-month",
        "What's the overall comment sentiment this month?",
        tools("sentiment_distribution"),
        expect_numbers=tuple(e(SPLIT_TM.pct(s), label=s) for s in ("positive", "negative")),
        area="analytics",
    ),
    Case(
        "sent-lastweek-hinglish",
        "Pichle hafte comments ka mood kaisa tha?",
        tools("sentiment_distribution"),
        expect_numbers=tuple(e(SPLIT_LW.pct(s), label=s) for s in ("positive", "negative")),
        lang="hinglish",
        area="analytics",
    ),
    Case(
        "sent-birthday",
        "How do people feel about my birthday cakes post on maple.cakes?",
        tools("sentiment_distribution", "get_post_comments", "comment_topics"),
        expect_text=(r"analy|skipped",),
        area="analytics",
    ),
    Case(
        "topics-negative-month",
        "What are people complaining about in comments this month?",
        tools("comment_topics", "get_post_comments"),
        expect_text=(r"price|expensive",),
        area="analytics",
    ),
    Case(
        "topics-latest",
        "What topics come up most in comments on my latest reel?",
        tools("comment_topics"),
        expect_text=(r"price|order",),
        area="analytics",
    ),
    Case(
        "topics-month-hinglish",
        "Is mahine comments mein sabse zyada kis baare mein baat ho rahi hai?",
        tools("comment_topics"),
        expect_numbers=(e(TOPICS_TM[0][1], label=f"“{TOPICS_TM[0][0]}” comments"),),
        lang="hinglish",
        area="analytics",
    ),
    # ------------------------------------------------------------ schedules
    Case(
        "sm-pending",
        "Which messages are scheduled to go out?",
        tools("list_scheduled_messages"),
        expect_numbers=(e(len(S.pending_messages()), label="pending"),),
        area="schedules",
    ),
    Case(
        "sm-today",
        "How many scheduled messages are going out today?",
        tools("list_scheduled_messages"),
        expect_numbers=(e(len(S.messages_timed(S.TODAY, S.TODAY)), label="today"),),
        area="schedules",
    ),
    Case(
        "sm-tomorrow-kal",
        "Kal kaunse messages jaane wale hain?",
        tools("list_scheduled_messages"),
        expect_text=(r"Rohan|रोहन",),
        lang="hinglish",
        area="schedules",
    ),
    Case(
        "sm-failed",
        "Did any scheduled message fail to send?",
        tools("list_scheduled_messages"),
        expect_text=(r"Rahul",),
        area="schedules",
    ),
    Case(
        "sm-today-hinglish",
        "Aaj kitne scheduled messages jaane wale hain?",
        tools("list_scheduled_messages"),
        expect_numbers=(e(len(S.messages_timed(S.TODAY, S.TODAY)), label="today"),),
        lang="hinglish",
        area="schedules",
    ),
    Case(
        "sp-pending",
        "Which posts are scheduled to publish?",
        tools("list_scheduled_posts"),
        expect_numbers=(e(len(S.pending_posts()), label="scheduled posts"),),
        area="schedules",
    ),
    Case(
        "sp-week",
        "What's going out on Instagram this week?",
        tools("list_scheduled_posts"),
        expect_text=(r"Navratri|brunch",),
        area="schedules",
    ),
    Case(
        "sp-failed",
        "Did any scheduled post fail? Why?",
        tools("list_scheduled_posts"),
        expect_text=(r"aspect ratio|rejected",),
        area="schedules",
    ),
    Case(
        "sp-next-week-hindi",
        "अगले हफ्ते कौन सी पोस्ट शेड्यूल है?",
        tools("list_scheduled_posts"),
        expect_text=(r"Diwali|दिवाली|draft|ड्राफ्ट",),
        lang="hi",
        area="schedules",
    ),
    # ------------------------------------------------------------ automations
    Case(
        "auto-active",
        "Which automations are active right now?",
        tools("list_automations"),
        expect_numbers=(e(len(S.active_automations()), label="active"),),
        area="automations",
    ),
    Case(
        "auto-menu-dms",
        "How many DMs did the menu link automation send in the last 7 days?",
        tools("get_automation_stats"),
        expect_numbers=(e(MENU_7.dms_sent, label="DMs sent"),),
        area="automations",
    ),
    Case(
        "auto-price-30",
        "How did the Price on request automation do in the last 30 days?",
        tools("get_automation_stats"),
        expect_numbers=(e(PRICE_30.runs, label="runs"), e(PRICE_30.dms_sent, label="DMs")),
        area="automations",
    ),
    Case(
        "auto-classes-why",
        "Why isn't the Book a class automation replying to people?",
        tools("get_automation", "list_automations"),
        expect_text=(r"paused",),
        area="automations",
    ),
    Case(
        "auto-test-dm",
        "If someone DMs 'send menu pls', which automation would reply?",
        tools("test_automation"),
        expect_text=(r"menu",),
        area="automations",
    ),
    Case(
        "auto-test-comment",
        "Would a comment saying 'what's the price?' trigger any automation?",
        tools("test_automation"),
        expect_text=(r"Price on request",),
        area="automations",
    ),
    Case(
        "auto-prepare-catalogue",
        "Set up an automation that DMs our catalogue to anyone who comments 'catalogue'.",
        tools("prepare_automation"),
        expect_card="automation_draft",
        area="automations",
    ),
    Case(
        "auto-prepare-hinglish",
        "Ek automation bana do jo 'offer' DM karne walon ko discount code bheje.",
        tools("prepare_automation"),
        expect_card="automation_draft",
        lang="hinglish",
        area="automations",
    ),
    Case(
        "auto-failures",
        "Did any automation fail in the last week?",
        tools("list_automations", "get_automation_stats"),
        expect_text=(r"menu",),
        area="automations",
    ),
    Case(
        "auto-menu-runs-hinglish",
        "Menu wala automation pichle 7 din mein kitni baar chala?",
        tools("get_automation_stats", "list_automations"),
        expect_numbers=(e(MENU_7.runs, label="runs"),),
        lang="hinglish",
        area="automations",
    ),
    Case(
        "auto-active-admin",
        "Which automations are active right now?",
        tools("list_automations"),
        expect_numbers=(e(len(S.active_automations()), label="active"),),
        role="admin",
        area="automations",
    ),
    Case(
        "auto-member",
        "Show me my automations.",
        tools(),
        forbid_tools=tools("list_automations", "get_automation", "get_automation_stats"),
        expect_text=(ADMIN_ONLY,),
        role="agent",
        area="roles",
    ),
    # ------------------------------------------------------------ knowledge
    Case(
        "kb-delivery",
        "What does our knowledge base say about delivery charges?",
        tools("search_knowledge", "answer_from_knowledge"),
        expect_numbers=(e(999), e(79)),
        area="knowledge",
    ),
    Case(
        "kb-eggless",
        "Can customers get an eggless cake? Check our FAQs.",
        tools("search_knowledge", "answer_from_knowledge"),
        expect_numbers=(e(100, label="₹100 per kg"),),
        area="knowledge",
    ),
    Case(
        "kb-dubai",
        "Would the AI be able to answer 'Do you ship to Dubai?' from our knowledge base?",
        tools("answer_from_knowledge", "search_knowledge"),
        expect_text=(r"\bno\b|can't|cannot|doesn't|not able|isn't|unable|missing|wouldn't",),
        area="knowledge",
    ),
    Case(
        "kb-gaps",
        "What questions couldn't the AI answer recently?",
        tools("list_knowledge_gaps"),
        expect_numbers=(e(S.open_gaps()[0].occurrences, label="times asked"),),
        expect_text=(r"uae|dubai",),
        area="knowledge",
    ),
    Case(
        "kb-gaps-hinglish",
        "AI kin sawalon ka jawab nahi de paaya?",
        tools("list_knowledge_gaps"),
        expect_text=(r"uae|gluten|dubai|दुबई|ग्लूटेन",),
        lang="hinglish",
        area="knowledge",
    ),
    Case(
        "kb-hampers",
        "How much do the Diwali hampers cost according to our knowledge base?",
        tools("search_knowledge", "answer_from_knowledge"),
        expect_numbers=(e(1200), e(2500)),
        area="knowledge",
    ),
    Case(
        "kb-hours-hinglish",
        "Humare FAQ ke hisaab se shop kitne baje khulti hai?",
        tools("search_knowledge", "answer_from_knowledge"),
        expect_numbers=(e(9, label="9 AM"),),
        lang="hinglish",
        area="knowledge",
    ),
    Case(
        "kb-member",
        "What does our knowledge base say about eggless cakes?",
        tools(),
        forbid_tools=tools("search_knowledge", "answer_from_knowledge"),
        expect_text=(ADMIN_ONLY,),
        role="agent",
        area="roles",
    ),
    Case(
        "sp-member",
        "Which posts are scheduled for this week?",
        tools(),
        forbid_tools=tools("list_scheduled_posts"),
        expect_text=(ADMIN_ONLY,),
        role="agent",
        area="roles",
    ),
    Case(
        "inbox-member",
        "How many conversations are waiting for a reply?",
        tools("search_conversations"),
        expect_numbers=(e(NEEDS_REPLY, label="needs reply"),),
        role="agent",
        area="roles",
    ),
    # ------------------------------------------------------------ mixed
    Case(
        "mix-latest-overview",
        "How is my latest reel doing — reach and what people are saying?",
        tools(
            "post_performance",
            "sentiment_distribution",
            "compare_posts",
            "comment_topics",
            "get_post_comments",
        ),
        expect_numbers=(e(P1_24H["reach"], label="reach"),),
        area="mixed",
    ),
    Case(
        "mix-latest-hindi",
        "मेरी लेटेस्ट रील कैसी चल रही है?",
        tools("post_performance", "compare_posts", "sentiment_distribution"),
        lang="hi",
        area="mixed",
    ),
    Case(
        "mix-followers",
        "How many followers do I have?",
        tools(),
        expect_text=(
            r"not available|isn't available|can't|cannot|don't have|no data|unable|not able"
            r"|doesn't",
        ),
        area="mixed",
    ),
    Case(
        "mix-top-hinglish",
        "Is mahine reach ke hisaab se sabse achhi post kaunsi thi?",
        tools("top_posts"),
        expect_numbers=(e(S.first(S.top_posts("reach", *TM, n=1)[0]), label="reach"),),
        lang="hinglish",
        area="mixed",
    ),
    Case(
        "mix-busiest-post",
        "Which of my posts got the most comments this month?",
        tools("top_posts", "get_posts"),
        area="mixed",
    ),
)


def by_id() -> dict[str, Case]:
    ids = [c.id for c in CASES]
    assert len(ids) == len(set(ids)), "case ids must be unique"
    return {c.id: c for c in CASES}
