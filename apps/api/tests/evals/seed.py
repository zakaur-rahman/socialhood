"""The Ask Social Hood eval workspace (TA.6): a bakery in Pune, seeded deterministically.

Everything is declared below as data (accounts, conversations, posts with their comments and
metric snapshots, automations with runs, scheduled messages and posts, knowledge and gaps,
members) at fixed times around ``NOW``: Wednesday 30 Sep 2026, 12:00 in Asia/Kolkata. ``seed``
writes it through the test factories (tests/support) and the ORM; the functions at the end
compute the answers the cases expect from the same declarations, by their own arithmetic (never
through the services the tools call), so a case checks the tools as well as the model.

Runs are pinned to ``NOW`` (the runner travels there for each case), so "last week" is always
21-27 Sep 2026 and the latest reel is always 26 hours old.
"""

from __future__ import annotations

import math
import statistics
import uuid
import zlib
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.agent import AgentPolicy
from socialhood.models.ai import AiSettings, MessageAnalysis
from socialhood.models.automations import AutomationRun, Comment
from socialhood.models.billing import Subscription
from socialhood.models.connections import SocialAccount
from socialhood.models.identity import User, Workspace, WorkspaceMember
from socialhood.models.inbox import Contact, Conversation, Message
from socialhood.models.media import MediaItem
from socialhood.platforms.instagram import oauth
from socialhood.repositories import comment_analyses
from tests.support.ai import make_gap, make_source
from tests.support.analytics import make_comment_analysis, make_snapshot
from tests.support.automations import make_automation, make_comment
from tests.support.inbox import make_asset, make_scheduled
from tests.support.post_metrics import make_post
from tests.support.publishing import make_scheduled_post

TIMEZONE = "Asia/Kolkata"
TZ = ZoneInfo(TIMEZONE)
WORKSPACE_NAME = "Maple Bakery"


def ist(month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0) -> datetime:
    """A time in the workspace's zone (2026), as UTC."""
    return datetime(2026, month, day, hour, minute, second, tzinfo=TZ).astimezone(UTC)


NOW = ist(9, 30, 12, 0)  # Wed 30 Sep 2026, 12:00 IST
TODAY = date(2026, 9, 30)


# ---------------------------------------------------------------- declarations


@dataclass(frozen=True)
class Account:
    key: str
    platform: Literal["instagram", "whatsapp"]
    platform_account_id: str
    username: str | None = None
    display_name: str | None = None
    phone_number: str | None = None
    insights: bool = False


ACCOUNTS = (
    Account("ig", "instagram", "17841499900000001", "maple.bakery", "Maple Bakery", insights=True),
    Account("ig2", "instagram", "17841499900000002", "maple.cakes", "Maple Cakes"),
    Account("wa", "whatsapp", "109900000000001", None, "Maple Bakery", "+91 98200 00000"),
)
ACCOUNT = {a.key: a for a in ACCOUNTS}


@dataclass(frozen=True)
class Msg:
    key: str
    at: datetime
    text: str
    sender: Literal["customer", "human", "automation"] = "customer"
    status: str | None = None  # outbound: "sent" unless given
    error: str | None = None

    @property
    def inbound(self) -> bool:
        return self.sender == "customer"


@dataclass(frozen=True)
class Reading:
    """The message analysis of the conversation's latest customer message (TR-AI-05)."""

    intent: str
    sentiment: str
    score: float
    priority: str
    lead_score: int
    language: str = "en"
    topics: tuple[str, ...] = ()
    needs_reply: bool = True
    needs_human: bool = False
    reason: str | None = None


@dataclass(frozen=True)
class Conv:
    key: str
    account: str
    name: str
    username: str | None  # Instagram handle; None on WhatsApp
    messages: tuple[Msg, ...]
    reading: Reading | None = None
    phone: str | None = None
    status: Literal["open", "archived"] = "open"
    awaiting_reply: bool = False
    closing_reminder: bool = False  # the follow-up reminder before the window closes is out
    summary: str | None = None
    next_step: str | None = None

    @property
    def platform(self) -> str:
        return ACCOUNT[self.account].platform

    @property
    def last(self) -> Msg:
        return max(self.messages, key=lambda m: m.at)

    @property
    def last_message_at(self) -> datetime:
        return self.last.at

    @property
    def last_inbound_at(self) -> datetime | None:
        inbound = [m.at for m in self.messages if m.inbound]
        return max(inbound) if inbound else None

    @property
    def last_outbound_at(self) -> datetime | None:
        outbound = [m.at for m in self.messages if not m.inbound]
        return max(outbound) if outbound else None

    @property
    def unread(self) -> int:
        """Customer messages after our last one, while a reply is awaited."""
        if not self.awaiting_reply:
            return 0
        after = self.last_outbound_at
        return sum(1 for m in self.messages if m.inbound and (after is None or m.at > after))

    @property
    def lead_score(self) -> int | None:
        return self.reading.lead_score if self.reading else None


def _m(key: str, at: datetime, body: str, sender: str = "customer", **kw: str) -> Msg:
    return Msg(key, at, body, sender, **kw)  # type: ignore[arg-type]


MENU_DM = "Hi {name}! Here's our menu: maplebakery.in/menu"
CLASS_DM = "Hi {name}! Book a class or a tasting here: maplebakery.in/classes"

CONVERSATIONS = (
    Conv(
        "priya_shah",
        "ig",
        "Priya Shah",
        "priya.shah",
        (
            _m("c1_menu", ist(9, 28, 17, 0), "Hi! Can you send me the menu link?"),
            _m("c1_dm", ist(9, 28, 17, 0, 30), MENU_DM.format(name="Priya"), "automation"),
            _m(
                "c1_ask",
                ist(9, 30, 10, 0),
                "Do you deliver to Baner? I want a chocolate truffle cake for Saturday.",
            ),
        ),
        Reading("purchase", "positive", 0.6, "high", 82, topics=("chocolate cake", "delivery")),
        awaiting_reply=True,
        summary="Priya wants a chocolate truffle cake delivered to Baner on Saturday.",
        next_step="Confirm delivery to Baner and share the price.",
    ),
    Conv(
        "priya_nair",
        "ig",
        "Priya Nair",
        "priya.bakes",
        (
            _m("c2_class", ist(9, 22, 15, 0), "Can I book a baking class?"),
            _m("c2_class_dm", ist(9, 22, 15, 0, 20), CLASS_DM.format(name="Priya"), "automation"),
            _m("c2_ask", ist(9, 27, 11, 0), "Do you sell your sourdough starter?"),
            _m(
                "c2_reply", ist(9, 27, 12, 0), "Not yet, but we're planning to next month!", "human"
            ),
        ),
        Reading("product_inquiry", "neutral", 0.0, "low", 35, topics=("sourdough starter",)),
    ),
    Conv(
        "rahul",
        "ig",
        "Rahul Mehta",
        "rahul.m",
        (
            _m("c3_a", ist(9, 29, 16, 0), "My order #1043 arrived damaged. I want a refund."),
            _m("c3_b", ist(9, 29, 16, 5), "This is really disappointing."),
        ),
        Reading(
            "refund",
            "negative",
            -0.8,
            "high",
            10,
            topics=("damaged order", "refund"),
            needs_human=True,
            reason="refund",
        ),
        awaiting_reply=True,
        closing_reminder=True,
        summary="Rahul's order #1043 arrived damaged and he wants a refund.",
        next_step="Apologise and arrange a refund or a replacement.",
    ),
    Conv(
        "ananya",
        "ig",
        "Ananya Gupta",
        "ananya.g",
        (
            _m("c4_menu", ist(9, 25, 20, 0), "menu bhejo please"),
            _m("c4_dm", ist(9, 25, 20, 0, 30), MENU_DM.format(name="Ananya"), "automation"),
            _m("c4_ask", ist(9, 29, 18, 0), "Kitne ka hai 1 kg chocolate truffle?"),
        ),
        Reading("pricing", "neutral", 0.1, "medium", 65, "hi-Latn", ("price",)),
        awaiting_reply=True,
    ),
    Conv(
        "karan",
        "ig2",
        "Karan Singh",
        "karan.s",
        (
            _m("c5_a", ist(9, 18, 14, 0), "Thanks for the lovely cake!"),
            _m("c5_b", ist(9, 18, 15, 0), "Thank you Karan! 🎂", "human"),
        ),
        Reading("feedback", "positive", 0.8, "low", 20, needs_reply=False),
        status="archived",
    ),
    Conv(
        "meera",
        "wa",
        "Meera Iyer",
        None,
        (
            _m(
                "c6_a",
                ist(9, 30, 7, 0),
                "Hi, can I order 50 cupcakes for an office party next Friday?",
            ),
        ),
        Reading("purchase", "positive", 0.5, "high", 90, topics=("cupcakes", "bulk order")),
        phone="919820111111",
        awaiting_reply=True,
    ),
    Conv(
        "arjun",
        "wa",
        "Arjun Das",
        None,
        (
            _m("c7_a", ist(9, 27, 19, 0), "Is the bakery open on Sunday?"),
            _m("c7_b", ist(9, 27, 19, 30), "Yes, 9 AM to 9 PM!", "human"),
            _m("c7_c", ist(9, 28, 9, 0), "Great, thanks"),
        ),
        Reading("feedback", "positive", 0.5, "low", 15, needs_reply=False),
        phone="919820222222",
    ),
    Conv(
        "sneha",
        "ig",
        "Sneha Kulkarni",
        "sneha.k",
        (
            _m("c8_menu", ist(9, 29, 9, 0), "Can I get the menu link?"),
            _m(
                "c8_dm",
                ist(9, 29, 9, 0, 30),
                MENU_DM.format(name="Sneha"),
                "automation",
                status="failed",
                error="Instagram couldn't deliver the message.",
            ),
            _m(
                "c8_ask", ist(9, 29, 10, 0), "Is the eggless option available for the truffle cake?"
            ),
        ),
        None,  # not analysed yet
        awaiting_reply=True,
    ),
    Conv(
        "vikas",
        "ig2",
        "Vikas Rao",
        "vikas.rao",
        (
            _m("c9_a", ist(9, 24, 13, 0), "Do you make sugar-free cakes?"),
            _m("c9_b", ist(9, 24, 14, 0), "Yes, sweetened with jaggery! Want details?", "human"),
        ),
        Reading("product_inquiry", "neutral", 0.1, "medium", 45, topics=("sugar-free cakes",)),
    ),
    Conv(
        "fatima",
        "ig",
        "Fatima Khan",
        "fatima.k",
        (
            _m("c10_a", ist(9, 10, 12, 0), "link"),
            _m("c10_dm", ist(9, 10, 12, 0, 30), MENU_DM.format(name="Fatima"), "automation"),
            _m("c10_b", ist(9, 10, 12, 10), "Thanks!"),
        ),
        Reading("feedback", "positive", 0.6, "low", 10, needs_reply=False),
        status="archived",
    ),
    Conv(
        "rohan",
        "wa",
        "Rohan Joshi",
        None,
        (
            _m(
                "c11_a",
                ist(9, 30, 11, 15),
                "Hi, do you ship to Dubai? I want to send a cake to my sister.",
            ),
        ),
        Reading("shipping", "neutral", 0.0, "medium", 50, topics=("shipping to uae",)),
        phone="919820333333",
        awaiting_reply=True,
    ),
    Conv(
        "divya",
        "ig",
        "Divya Menon",
        "divya.m",
        (
            _m("c12_class", ist(9, 20, 16, 0), "Can I book a tasting session?"),
            _m("c12_class_dm", ist(9, 20, 16, 0, 20), CLASS_DM.format(name="Divya"), "automation"),
            _m("c12_menu", ist(9, 28, 10, 0), "Please share the menu"),
            _m("c12_dm", ist(9, 28, 10, 0, 30), MENU_DM.format(name="Divya"), "automation"),
            _m("c12_b", ist(9, 28, 10, 30), "Thanks! I'll order the Diwali hamper."),
            _m("c12_c", ist(9, 28, 11, 0), "Lovely! Let us know the date.", "human"),
            _m(
                "c12_sched", ist(9, 29, 11, 0), "Reminder: Diwali hampers ship from 5 Oct.", "human"
            ),
        ),
        Reading("purchase", "positive", 0.7, "medium", 70, topics=("diwali hamper",)),
    ),
    Conv(
        "neha",
        "ig",
        "Neha Bakes",
        "neha.bakes",
        (
            _m(
                "c13_dm",
                ist(9, 29, 10, 46),
                "Hi Neha! Our chocolate truffle cake is ₹1,450 per kg. Want to pre-order?",
                "automation",
            ),
            _m("c13_a", ist(9, 29, 11, 10), "Yes! 1 kg for Saturday please"),
            _m("c13_b", ist(9, 29, 12, 0), "Done! Booked for Saturday, 11 AM.", "human"),
        ),
        Reading("purchase", "positive", 0.8, "high", 75, topics=("pre-order",)),
    ),
    Conv(
        "rohit",
        "ig",
        "Rohit Bhatt",
        "rohit.b",
        (
            _m(
                "c14_dm",
                ist(9, 26, 19, 6),
                "Hi Rohit! The blueberry cheesecake is ₹900. Want one?",
                "automation",
            ),
        ),
    ),
)
CONVERSATION = {c.key: c for c in CONVERSATIONS}
MESSAGE = {m.key: (c, m) for c in CONVERSATIONS for m in c.messages}


@dataclass(frozen=True)
class Cmt:
    key: str
    at: datetime
    author: str
    text: str
    # (sentiment, intent, topic); None: still being analysed
    reading: tuple[str, str, str | None] | None = None
    spam: bool = False
    skipped: bool = False  # not analysed (beyond the plan, credits used up)
    reply: str | None = None  # our public reply
    replied_at: datetime | None = None
    contact: str | None = None  # the commenter's conversation

    @property
    def analysed(self) -> bool:
        return self.reading is not None and not self.skipped


def _c(
    key: str,
    at: datetime,
    author: str,
    body: str,
    sentiment: str | None = None,
    intent: str = "other",
    topic: str | None = None,
    **kw: object,
) -> Cmt:
    reading = (sentiment, intent, topic) if sentiment else None
    return Cmt(key, at, author, body, reading, **kw)  # type: ignore[arg-type]


def _spam(key: str, at: datetime, author: str, body: str) -> Cmt:
    return Cmt(key, at, author, body, ("neutral", "spam", None), spam=True)


@dataclass(frozen=True)
class Post:
    key: str
    account: str
    media_type: Literal["image", "carousel", "reel"]
    caption: str
    posted_at: datetime
    final: dict[str, int]  # reach, views, likes, shares, saves at 30 days
    comments: tuple[Cmt, ...] = ()

    @property
    def format(self) -> str:
        return "reel" if self.media_type == "reel" else "feed"


def _final(reach: int, views: int, likes: int, shares: int, saves: int) -> dict[str, int]:
    return {"reach": reach, "views": views, "likes": likes, "shares": shares, "saves": saves}


POSTS = (
    Post(
        "p1",
        "ig",
        "reel",
        "Chocolate truffle cake reveal 🍫 Pre-orders open for the weekend #cake #pune",
        ist(9, 29, 10, 0),
        _final(5500, 9200, 520, 56, 78),
        (
            _c(
                "c1",
                ist(9, 29, 10, 20),
                "foodie.pune",
                "This looks insane 😍",
                "positive",
                "feedback",
                "cake look",
            ),
            _c(
                "c2",
                ist(9, 29, 10, 45),
                "neha.bakes",
                "Price for 1 kg?",
                "neutral",
                "pricing",
                "price",
                reply="Sent you the details in DM!",
                replied_at=ist(9, 29, 10, 46),
                contact="neha",
            ),
            _c(
                "c3",
                ist(9, 29, 11, 30),
                "amit.k",
                "Too expensive compared to last time",
                "negative",
                "complaint",
                "price",
            ),
            _c(
                "c4",
                ist(9, 29, 13, 0),
                "riya.s",
                "Ordered one, can't wait!",
                "positive",
                "purchase",
                "order",
            ),
            _c(
                "c5",
                ist(9, 29, 15, 10),
                "sanjay.v",
                "Delivery was late last time, hope it's better",
                "negative",
                "complaint",
                "delivery",
            ),
            _c(
                "c6",
                ist(9, 29, 18, 0),
                "meenal.d",
                "Bahut tasty lag raha hai",
                "positive",
                "feedback",
                "taste",
            ),
            _spam("c7", ist(9, 29, 20, 30), "promo.deals", "Get 10k followers cheap, DM us"),
            _c(
                "c8",
                ist(9, 30, 8, 15),
                "karthik.r",
                "Is there an eggless version?",
                "neutral",
                "product_inquiry",
                "eggless",
            ),
            _c(
                "c9",
                ist(9, 30, 9, 40),
                "priya.shah",
                "Booked mine for Saturday!",
                "positive",
                "purchase",
                "order",
                contact="priya_shah",
            ),
            _c("c10", ist(9, 30, 11, 20), "lakshmi.n", "Kitne din pehle order karna hoga?"),
        ),
    ),
    Post(
        "p2",
        "ig",
        "image",
        "Weekend special: blueberry cheesecake 🫐",
        ist(9, 26, 18, 0),
        _final(2900, 3800, 260, 14, 33),
        (
            _c(
                "d1",
                ist(9, 26, 18, 30),
                "anita.p",
                "Yum! Saving this",
                "positive",
                "feedback",
                "taste",
            ),
            _c(
                "d2",
                ist(9, 26, 19, 5),
                "rohit.b",
                "What's the price?",
                "neutral",
                "pricing",
                "price",
                reply="Sent you the details in DM!",
                replied_at=ist(9, 26, 19, 6),
                contact="rohit",
            ),
            _c(
                "d3",
                ist(9, 27, 10, 0),
                "jaya.m",
                "₹900 is a lot for a small cheesecake",
                "negative",
                "complaint",
                "price",
            ),
            _c(
                "d4",
                ist(9, 27, 12, 30),
                "vivek.t",
                "Best cheesecake in Pune",
                "positive",
                "feedback",
                "taste",
            ),
            _c(
                "d5",
                ist(9, 28, 9, 0),
                "sara.k",
                "Do you deliver to Wakad?",
                "neutral",
                "shipping",
                "delivery area",
            ),
            _c("d6", ist(9, 29, 21, 0), "om.prakash", "Kya ye weekend pe bhi milega?"),
        ),
    ),
    Post(
        "p3",
        "ig",
        "carousel",
        "Diwali gift hampers are here 🪔 Pre-order now, limited stock",
        ist(9, 21, 11, 0),
        _final(4000, 5800, 330, 26, 90),
        (
            _c("e1", ist(9, 21, 11, 30), "kavya.r", "Price please?", "neutral", "pricing", "price"),
            _c("e2", ist(9, 21, 12, 0), "manish.g", "Price?", "neutral", "pricing", "price"),
            _c(
                "e3",
                ist(9, 21, 14, 0),
                "deepa.s",
                "Beautiful hampers!",
                "positive",
                "feedback",
                "hampers",
                reply="Thank you Deepa!",
                replied_at=ist(9, 21, 15, 0),
            ),
            _c(
                "e4",
                ist(9, 22, 10, 0),
                "arun.k",
                "₹2,500 for this? Too expensive",
                "negative",
                "complaint",
                "price",
            ),
            _c(
                "e5",
                ist(9, 23, 16, 0),
                "ishita.m",
                "Ordered two for my office",
                "positive",
                "purchase",
                "order",
            ),
            _c(
                "e6",
                ist(9, 24, 9, 30),
                "tanvi.j",
                "Packaging looks premium",
                "positive",
                "feedback",
                "packaging",
            ),
            _spam("e7", ist(9, 25, 18, 0), "cheap.followers", "Boost your page!! link in bio"),
            _c(
                "e8",
                ist(9, 26, 11, 0),
                "nikhil.c",
                "Overpriced tbh",
                "negative",
                "complaint",
                "price",
            ),
            _c(
                "e9",
                ist(9, 27, 20, 0),
                "ankit.s",
                "When is delivery?",
                "neutral",
                "shipping",
                "delivery",
            ),
        ),
    ),
    Post(
        "p4",
        "ig",
        "reel",
        "How we make our butter croissants 🥐",
        ist(9, 15, 19, 0),
        _final(5200, 9800, 430, 61, 75),
        (
            _c(
                "f1",
                ist(9, 15, 19, 30),
                "chef.anu",
                "So flaky!",
                "positive",
                "feedback",
                "croissants",
            ),
            _c("f2", ist(9, 15, 21, 0), "raj.b", "Recipe please", "neutral", "other", "recipe"),
            _c(
                "f3",
                ist(9, 16, 8, 0),
                "neha.bakes",
                "Loved these",
                "positive",
                "feedback",
                "taste",
                contact="neha",
            ),
            _c(
                "f4",
                ist(9, 16, 10, 0),
                "guest.99",
                "Came in the morning, sold out 😞",
                "negative",
                "complaint",
                "stock",
            ),
            _c(
                "f5",
                ist(9, 17, 12, 0),
                "ritu.a",
                "Best croissants",
                "positive",
                "feedback",
                "taste",
            ),
        ),
    ),
    Post(
        "p5",
        "ig",
        "image",
        "New menu: savoury pies 🥧",
        ist(9, 8, 13, 0),
        _final(1600, 2200, 120, 5, 10),
        (
            _c(
                "g1",
                ist(9, 8, 14, 0),
                "sameer.q",
                "Chicken pie when?",
                "neutral",
                "product_inquiry",
                "menu",
            ),
            _c(
                "g2",
                ist(9, 9, 10, 0),
                "tina.l",
                "My order came 2 hours late",
                "negative",
                "complaint",
                "delivery",
            ),
            _c("g3", ist(9, 10, 15, 0), "harsh.v", "Looks good", "positive", "feedback", "menu"),
        ),
    ),
    Post(
        "p6",
        "ig",
        "reel",
        "Behind the scenes: 5 AM baking",
        ist(8, 26, 19, 0),
        _final(3100, 5300, 270, 23, 31),
        (
            _c(
                "h1", ist(8, 27, 9, 0), "early.bird", "Respect 🙌", "positive", "feedback", "bakers"
            ),
            _c("h2", ist(8, 28, 10, 0), "sleepy.cat", "Why so early", "neutral", "other"),
        ),
    ),
    Post(
        "p7",
        "ig",
        "reel",
        "Monsoon special: masala chai cookies",
        ist(8, 11, 19, 0),
        _final(2500, 4400, 210, 16, 21),
        (
            _c(
                "i1",
                ist(8, 12, 9, 0),
                "chai.lover",
                "Need these now",
                "positive",
                "purchase",
                "cookies",
            ),
        ),
    ),
    Post(
        "p8",
        "ig2",
        "image",
        "Custom birthday cakes — DM to order 🎂",
        ist(9, 27, 9, 0),
        _final(0, 0, 110, 0, 0),
        (
            _c(
                "k1",
                ist(9, 27, 10, 0),
                "mom.of.two",
                "Need one for my son's 5th birthday",
                "neutral",
                "purchase",
                "custom cake",
            ),
            _c(
                "k2",
                ist(9, 27, 14, 0),
                "party.planner",
                "Do you do fondant?",
                "neutral",
                "product_inquiry",
                "fondant",
            ),
            _c("k3", ist(9, 28, 11, 0), "happy.kid", "So cute!!", "positive", "feedback", "design"),
            Cmt("k4", ist(9, 29, 16, 0), "late.reply", "Price list?", skipped=True),
        ),
    ),
    Post(
        "p9",
        "ig",
        "reel",
        "Sourdough 101 🍞",
        ist(9, 5, 12, 0),
        _final(3400, 6200, 300, 31, 45),
        (
            _c(
                "j1",
                ist(9, 5, 13, 0),
                "bread.lover",
                "Teach a class!",
                "positive",
                "collaboration",
                "classes",
            ),
            _c(
                "j2",
                ist(9, 6, 9, 0),
                "anon.user",
                "Too sour for me",
                "negative",
                "feedback",
                "taste",
            ),
        ),
    ),
)
POST = {p.key: p for p in POSTS}
COMMENT = {c.key: (p, c) for p in POSTS for c in p.comments}


@dataclass(frozen=True)
class Run:
    at: datetime
    trigger: str  # a message key (DM triggers) or a comment key (comment triggers)
    result: str = "sent"
    dm: str | None = None  # the message key of the DM it sent
    public_reply: bool = False
    replied_at: datetime | None = None  # the contact wrote back within 24 hours


@dataclass(frozen=True)
class AutomationSpec:
    key: str
    name: str
    status: Literal["active", "paused", "draft"]
    trigger: str
    keywords: tuple[str, ...]
    message_text: str
    activated_at: datetime
    runs: tuple[Run, ...]
    public_replies: tuple[str, ...] = ()
    paused_at: datetime | None = None


AUTOMATIONS = (
    AutomationSpec(
        "menu",
        "Send the menu link",
        "active",
        "dm_keyword",
        ("menu", "link"),
        "Hi {first_name}! Here's our menu: maplebakery.in/menu",
        ist(9, 1, 10, 0),
        (
            Run(ist(9, 28, 17, 0), "c1_menu", dm="c1_dm"),
            Run(ist(9, 25, 20, 0), "c4_menu", dm="c4_dm"),
            Run(ist(9, 29, 9, 0), "c8_menu", "failed", dm="c8_dm"),
            Run(ist(9, 10, 12, 0), "c10_a", dm="c10_dm"),
            Run(ist(9, 28, 10, 0), "c12_menu", dm="c12_dm", replied_at=ist(9, 28, 10, 30)),
        ),
    ),
    AutomationSpec(
        "price",
        "Price on request",
        "active",
        "comment_keyword",
        ("price",),
        "Hi {first_name}! Here are our prices for this one. Want to pre-order?",
        ist(9, 15, 10, 0),
        (
            Run(ist(9, 29, 10, 45), "c2", dm="c13_dm", public_reply=True),
            Run(ist(9, 26, 19, 5), "d2", dm="c14_dm", public_reply=True),
            Run(ist(9, 21, 11, 30), "e1", "failed"),
            Run(ist(9, 21, 12, 0), "e2", "skipped_cooldown"),
        ),
        public_replies=("Sent you the details in DM!",),
    ),
    AutomationSpec(
        "classes",
        "Book a class",
        "paused",
        "dm_keyword",
        ("class", "tasting", "book"),
        "Hi {first_name}! Book a class or a tasting here: maplebakery.in/classes",
        ist(9, 1, 10, 0),
        (
            Run(ist(9, 22, 15, 0), "c2_class", dm="c2_class_dm"),
            Run(ist(9, 20, 16, 0), "c12_class", dm="c12_class_dm"),
        ),
        paused_at=ist(9, 25, 9, 0),
    ),
)
AUTOMATION = {a.key: a for a in AUTOMATIONS}


@dataclass(frozen=True)
class ScheduledMsg:
    key: str
    conversation: str
    text: str
    send_at: datetime
    status: str = "scheduled"
    message: str | None = None  # the message it became (sent)
    error: str | None = None


SCHEDULED_MESSAGES = (
    ScheduledMsg(
        "sm1",
        "priya_shah",
        "Your chocolate truffle cake is confirmed for Saturday 🎂",
        ist(9, 30, 17, 0),
    ),
    ScheduledMsg("sm2", "meera", "Sharing our cupcake menu and bulk prices.", ist(9, 30, 20, 0)),
    ScheduledMsg(
        "sm3", "rohan", "We'll confirm Dubai shipping options by tomorrow.", ist(10, 1, 9, 0)
    ),
    ScheduledMsg(
        "sm4",
        "divya",
        "Reminder: Diwali hampers ship from 5 Oct.",
        ist(9, 29, 11, 0),
        "sent",
        message="c12_sched",
    ),
    ScheduledMsg(
        "sm5", "ananya", "1 kg chocolate truffle is ₹1,450.", ist(9, 30, 9, 0), "canceled"
    ),
    ScheduledMsg(
        "sm6",
        "rahul",
        "Following up on your refund request.",
        ist(9, 29, 20, 0),
        "failed",
        error="Instagram didn't accept the message. Try again.",
    ),
)


@dataclass(frozen=True)
class ScheduledPostSpec:
    key: str
    caption: str
    status: str
    publish_at: datetime
    targets: tuple[tuple[str, str], ...]  # (account key, target status)
    assets: int = 1
    error: str | None = None


SCHEDULED_POSTS = (
    ScheduledPostSpec(
        "sp1",
        "Navratri special: thandai cookies 🌼",
        "scheduled",
        ist(10, 1, 18, 0),
        (("ig", "pending"),),
    ),
    ScheduledPostSpec(
        "sp2",
        "Weekend brunch box is back ☕",
        "scheduled",
        ist(10, 3, 11, 0),
        (("ig", "pending"), ("ig2", "pending")),
        assets=2,
    ),
    ScheduledPostSpec(
        "sp3",
        "Diwali countdown: 20 days to go 🪔",
        "draft",
        ist(10, 6, 19, 0),
        (("ig", "pending"),),
    ),
    ScheduledPostSpec(
        "sp4",
        "Weekend special: blueberry cheesecake 🫐",
        "published",
        ist(9, 26, 18, 0),
        (("ig", "published"),),
    ),
    ScheduledPostSpec(
        "sp5",
        "Sunday offer on custom cakes 🎂",
        "failed",
        ist(9, 29, 15, 0),
        (("ig2", "failed"),),
        error="Instagram rejected the image: its aspect ratio isn't supported.",
    ),
)


@dataclass(frozen=True)
class Faq:
    question: str
    answer: str


KNOWLEDGE = (
    Faq(
        "What are your delivery charges?",
        "Delivery is free in Pune on orders above ₹999; below that it is ₹79. We deliver across "
        "Pune city only.",
    ),
    Faq("Do you have eggless cakes?", "Yes. Every cake can be made eggless for ₹100 extra per kg."),
    Faq(
        "How early should I order a custom cake?",
        "Order custom cakes at least 3 days in advance; wedding cakes need 2 weeks.",
    ),
    Faq("What are your opening hours?", "We are open every day from 9 AM to 9 PM, Sundays too."),
    Faq(
        "How much are the Diwali hampers?",
        "Diwali hampers cost ₹1,200 (small) and ₹2,500 (large). They ship from 5 Oct and "
        "pre-orders close on 25 Oct.",
    ),
)


@dataclass(frozen=True)
class GapSpec:
    topic: str
    occurrences: int
    first_seen_at: datetime
    last_seen_at: datetime
    examples: tuple[str, ...] = ()  # message keys
    status: str = "open"


GAPS = (
    GapSpec("shipping to uae", 3, ist(9, 20, 10, 0), ist(9, 30, 11, 15), ("c11_a",)),
    GapSpec("gluten free options", 2, ist(9, 25, 12, 0), ist(9, 27, 14, 0)),
    GapSpec("franchise enquiry", 4, ist(7, 30, 12, 0), ist(8, 15, 12, 0)),  # older than 30 days
    GapSpec("wedding cake tasting", 1, ist(9, 23, 12, 0), ist(9, 23, 12, 0), status="dismissed"),
)


@dataclass(frozen=True)
class Member:
    role: Literal["owner", "admin", "agent"]
    name: str
    email: str


MEMBERS = (
    Member("owner", "Asha Rao", "asha@maplebakery.example"),
    Member("admin", "Vikram Iyer", "vikram@maplebakery.example"),
    Member("agent", "Kabir Malhotra", "kabir@maplebakery.example"),
)


# ---------------------------------------------------------------- metric snapshots (FR-ANL-01)

WINDOW_AGES = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "72h": timedelta(hours=72),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}
LIVE_WINDOWS = ("1h", "6h")  # likes and comments only
CURVE = {"1h": 0.15, "6h": 0.45, "24h": 0.75, "72h": 0.9, "7d": 0.97, "30d": 1.0}
INSIGHT_NAMES = ("reach", "views", "shares", "saves")


def _round(value: float) -> int:
    return math.floor(value + 0.5)


def windows_of(post: Post) -> list[str]:
    """The windows the post has reached by NOW (each was captured when due)."""
    return [w for w, age in WINDOW_AGES.items() if post.posted_at + age <= NOW]


def comments_by(post: Post, at: datetime) -> int:
    return sum(1 for c in post.comments if c.at <= at)


def metrics_at(post: Post, window: str) -> dict[str, int]:
    """The snapshot's figures: likes on the curve, comments counted from the rows made by then,
    and (24 hours on, with insights) reach, views, shares, saves and total interactions."""
    share = CURVE[window]
    values = {
        "likes": _round(post.final["likes"] * share),
        "comments": comments_by(post, post.posted_at + WINDOW_AGES[window]),
    }
    if window not in LIVE_WINDOWS and ACCOUNT[post.account].insights:
        values |= {name: _round(post.final[name] * share) for name in INSIGHT_NAMES}
        values["total_interactions"] = (
            values["likes"] + values["comments"] + values["shares"] + values["saves"]
        )
    return values


def insights_final(post: Post) -> bool:
    """The 72-hour reading marks the earlier ones final."""
    return "72h" in windows_of(post)


# ---------------------------------------------------------------- writing it


@dataclass
class Seeded:
    workspace_id: uuid.UUID
    users: dict[str, uuid.UUID]  # role -> user id
    accounts: dict[str, uuid.UUID]
    conversations: dict[str, uuid.UUID]
    contacts: dict[str, uuid.UUID]
    messages: dict[str, uuid.UUID]
    posts: dict[str, uuid.UUID]
    comments: dict[str, uuid.UUID]
    automations: dict[str, uuid.UUID]
    scheduled_messages: dict[str, uuid.UUID] = field(default_factory=dict)
    scheduled_posts: dict[str, uuid.UUID] = field(default_factory=dict)


async def wipe(engine: AsyncEngine) -> None:
    """Empty every tenant table (the same statement the API tests use), so the eval workspace is
    the only one."""
    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE users, workspaces, webhook_events, data_deletion_requests CASCADE")
        )


async def seed(engine: AsyncEngine) -> Seeded:
    """Write the workspace. Call on an empty database (``wipe``)."""
    users: dict[str, uuid.UUID] = {}
    async with AsyncSession(engine, expire_on_commit=False) as session:
        for member in MEMBERS:
            user = User(
                clerk_user_id=f"user_eval_{member.role}", email=member.email, name=member.name
            )
            session.add(user)
            await session.flush()
            users[member.role] = user.id
        workspace = Workspace(
            name=WORKSPACE_NAME,
            slug="maple-bakery-eval",
            timezone=TIMEZONE,
            owner_user_id=users["owner"],
        )
        session.add(workspace)
        await session.commit()
        wid = workspace.id

    with workspace_scope(wid):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            for member in MEMBERS:
                session.add(WorkspaceMember(user_id=users[member.role], role=member.role))
            session.add(
                Subscription(
                    plan="max",
                    status="active",
                    billing_anchor_day=1,
                    current_period_start=ist(9, 1),
                    current_period_end=ist(10, 1),
                )
            )
            session.add(
                AiSettings(
                    business_name=WORKSPACE_NAME,
                    business_description=(
                        "A home bakery in Pune selling cakes, cookies, breads and festive hampers"
                    ),
                    tone="friendly",
                )
            )
            session.add(AgentPolicy())
            accounts: dict[str, uuid.UUID] = {}
            for spec in ACCOUNTS:
                scopes = [*oauth.BASE_SCOPES, *([oauth.INSIGHTS_SCOPE] if spec.insights else [])]
                acct = SocialAccount(
                    platform=spec.platform,
                    platform_account_id=spec.platform_account_id,
                    username=spec.username,
                    display_name=spec.display_name,
                    phone_number=spec.phone_number,
                    status="active",
                    scopes=scopes if spec.platform == "instagram" else [],
                    connected_at=ist(7, 1),
                    connected_by_user_id=users["owner"],
                )
                session.add(acct)
                await session.flush()
                accounts[spec.key] = acct.id
            conversations, contacts, messages = await _inbox(session, accounts)
            await session.commit()

    posts: dict[str, uuid.UUID] = {}
    comments: dict[str, uuid.UUID] = {}
    for post in POSTS:
        latest = windows_of(post)[-1]
        lifetime = metrics_at(post, latest)
        post_id = await make_post(
            engine,
            workspace_id=wid,
            account_id=accounts[post.account],
            posted_at=post.posted_at,
            media_type=post.media_type,
            platform_media_id=f"1810999{len(posts):06d}",
            caption=post.caption,
            like_count=lifetime["likes"],
            comments_count=len(post.comments),
        )
        posts[post.key] = post_id
        for window in windows_of(post):
            await make_snapshot(
                engine,
                workspace_id=wid,
                media_item_id=post_id,
                window=window,
                metrics=metrics_at(post, window),
                insights_final=insights_final(post),
                captured_at=post.posted_at + WINDOW_AGES[window],
            )
        for c in post.comments:
            comment_id = await make_comment(
                engine,
                workspace_id=wid,
                account_id=accounts[post.account],
                media_item_id=post_id,
                text=c.text,
                author_ref=f"99{zlib.crc32(c.author.encode()):012d}",
                author_username=c.author,
                commented_at=c.at,
                contact_id=contacts.get(c.contact) if c.contact else None,
            )
            comments[c.key] = comment_id
            if c.reading is not None and not c.skipped:
                sentiment, intent, topic = c.reading
                score = {"positive": 0.7, "neutral": 0.0, "negative": -0.6}[sentiment]
                await make_comment_analysis(
                    engine,
                    workspace_id=wid,
                    comment_id=comment_id,
                    sentiment=sentiment,
                    sentiment_score=score,
                    intent=intent,
                    is_spam=c.spam,
                    topic=topic,
                    prompt_version="comment_analysis.v1",
                )
    with workspace_scope(wid):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            for p in POSTS:
                for c in p.comments:
                    row = await session.get(Comment, comments[c.key])
                    assert row is not None
                    row.like_count = len(c.text) % 7
                    if c.skipped:
                        row.analysis_status = "skipped"
                    if c.reply:
                        row.our_reply_text = c.reply
                        row.our_replied_at = c.replied_at
                        row.our_reply_platform_id = f"1790999{c.key}"
            await session.flush()
            await comment_analyses.recount(session, list(posts.values()))
            for item_key, item_id in posts.items():
                item = await session.get(MediaItem, item_id)
                assert item is not None
                item.synced_at = NOW - timedelta(minutes=10)
                item.permalink = f"https://www.instagram.com/p/maple{item_key}/"
            await session.commit()

    automations = await _automations(engine, wid, accounts, messages, comments, contacts)
    seeded = Seeded(
        workspace_id=wid,
        users=users,
        accounts=accounts,
        conversations=conversations,
        contacts=contacts,
        messages=messages,
        posts=posts,
        comments=comments,
        automations=automations,
    )
    await _schedules(engine, seeded)
    await _knowledge(engine, seeded)
    return seeded


async def _inbox(
    session: AsyncSession, accounts: dict[str, uuid.UUID]
) -> tuple[dict[str, uuid.UUID], dict[str, uuid.UUID], dict[str, uuid.UUID]]:
    conversations: dict[str, uuid.UUID] = {}
    contacts: dict[str, uuid.UUID] = {}
    messages: dict[str, uuid.UUID] = {}
    for n, spec in enumerate(CONVERSATIONS):
        acct_id = accounts[spec.account]
        first = min(m.at for m in spec.messages)
        contact = Contact(
            social_account_id=acct_id,
            platform_user_id=spec.phone or f"igsid_eval_{n:04d}",
            username=spec.username,
            display_name=spec.name,
            first_seen_at=first,
            last_seen_at=spec.last_inbound_at or first,
            follows_business=True if spec.platform == "instagram" else None,
        )
        session.add(contact)
        await session.flush()
        contacts[spec.key] = contact.id
        last = spec.last
        reading = spec.reading
        conv = Conversation(
            social_account_id=acct_id,
            contact_id=contact.id,
            platform=spec.platform,
            status=spec.status,
            last_message_at=last.at,
            last_inbound_at=spec.last_inbound_at,
            last_outbound_at=spec.last_outbound_at,
            last_message_preview=last.text[:200],
            last_message_direction="inbound" if last.inbound else "outbound",
            last_message_source=last.sender,
            last_message_kind="text",
            unread_count=spec.unread,
            awaiting_reply=spec.awaiting_reply,
            needs_human=bool(reading and reading.needs_human),
            needs_human_reason=reading.reason if reading else None,
            last_intent=reading.intent if reading else None,
            last_sentiment=reading.sentiment if reading else None,
            priority=reading.priority if reading else None,
            lead_score=reading.lead_score if reading else None,
            summary=spec.summary,
            summary_next_step=spec.next_step,
            summary_updated_at=last.at if spec.summary else None,
            window_reminder_for=spec.last_inbound_at if spec.closing_reminder else None,
        )
        session.add(conv)
        await session.flush()
        conversations[spec.key] = conv.id
        for m in sorted(spec.messages, key=lambda m: m.at):
            status = "received" if m.inbound else (m.status or "sent")
            row = Message(
                conversation_id=conv.id,
                social_account_id=acct_id,
                direction="inbound" if m.inbound else "outbound",
                source=m.sender,
                kind="text",
                text=m.text,
                occurred_at=m.at,
                platform_message_id=None if status == "failed" else f"mid_eval_{m.key}",
                status=status,
                sent_at=m.at if status == "sent" else None,
                error_message=m.error,
                error_code="platform_rejected" if m.error else None,
                attempts=0 if m.inbound else 1,
            )
            session.add(row)
            await session.flush()
            messages[m.key] = row.id
        if reading is not None:
            target = max((m for m in spec.messages if m.inbound), key=lambda m: m.at)
            session.add(
                MessageAnalysis(
                    message_id=messages[target.key],
                    conversation_id=conv.id,
                    intent=reading.intent,
                    sentiment=reading.sentiment,
                    sentiment_score=reading.score,
                    priority=reading.priority,
                    lead_score=reading.lead_score,
                    language=reading.language,
                    topics=list(reading.topics),
                    needs_reply=reading.needs_reply,
                    needs_human=reading.needs_human,
                    needs_human_reason=reading.reason,
                    model="gemini-3.5-flash-lite",
                    prompt_version="analysis.v1",
                    input_tokens=400,
                    output_tokens=60,
                    latency_ms=900,
                )
            )
    await session.flush()
    return conversations, contacts, messages


async def _automations(
    engine: AsyncEngine,
    wid: uuid.UUID,
    accounts: dict[str, uuid.UUID],
    messages: dict[str, uuid.UUID],
    comments: dict[str, uuid.UUID],
    contacts: dict[str, uuid.UUID],
) -> dict[str, uuid.UUID]:
    ids: dict[str, uuid.UUID] = {}
    for spec in AUTOMATIONS:
        values: dict[str, object] = {
            "name": spec.name,
            "status": spec.status,
            "trigger": spec.trigger,
            "action": "send_message",
            "message_text": spec.message_text,
            "public_reply_texts": list(spec.public_replies),
            "activated_at": spec.activated_at,
            "paused_at": spec.paused_at,
            "last_run_at": max(r.at for r in spec.runs) if spec.runs else None,
        }
        ids[spec.key] = await make_automation(
            engine,
            workspace_id=wid,
            account_id=accounts["ig"],
            keywords=spec.keywords,
            **values,
        )
    with workspace_scope(wid):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            for spec in AUTOMATIONS:
                for run in spec.runs:
                    by_message = run.trigger in MESSAGE
                    if by_message:
                        conv, _ = MESSAGE[run.trigger]
                        contact_key: str | None = conv.key
                    else:
                        _, c = COMMENT[run.trigger]
                        contact_key = c.contact
                    dm_conv = MESSAGE[run.dm][0].key if run.dm else None
                    keyword = next(
                        (
                            k
                            for k in spec.keywords
                            if k
                            in (
                                MESSAGE[run.trigger][1].text
                                if by_message
                                else COMMENT[run.trigger][1].text
                            ).casefold()
                        ),
                        spec.keywords[0],
                    )
                    session.add(
                        AutomationRun(
                            automation_id=ids[spec.key],
                            contact_id=contacts.get(contact_key) if contact_key else None,
                            conversation_id=(
                                await _conversation_id(session, contacts, dm_conv or contact_key)
                            ),
                            trigger_message_id=messages[run.trigger] if by_message else None,
                            trigger_comment_id=None if by_message else comments[run.trigger],
                            matched_keyword=keyword,
                            result=run.result,
                            private_reply_message_id=messages[run.dm] if run.dm else None,
                            public_reply_platform_id=(
                                f"1790999pub{run.trigger}" if run.public_reply else None
                            ),
                            contact_replied_at=run.replied_at,
                            error_code="platform_rejected" if run.result == "failed" else None,
                            error_message=(
                                "Instagram couldn't deliver the message."
                                if run.result == "failed"
                                else None
                            ),
                            created_at=run.at,
                        )
                    )
            await session.commit()
    return ids


async def _conversation_id(
    session: AsyncSession, contacts: dict[str, uuid.UUID], key: str | None
) -> uuid.UUID | None:
    if key is None:
        return None
    conv = (
        await session.execute(
            text("SELECT id FROM conversations WHERE contact_id = :c"), {"c": contacts[key]}
        )
    ).scalar_one_or_none()
    return conv


async def _schedules(engine: AsyncEngine, seeded: Seeded) -> None:
    wid = seeded.workspace_id
    for spec in SCHEDULED_MESSAGES:
        sid = await make_scheduled(
            engine,
            workspace_id=wid,
            conversation_id=seeded.conversations[spec.conversation],
            text=spec.text,
            send_at=spec.send_at,
            status=spec.status,
        )
        seeded.scheduled_messages[spec.key] = sid
        if spec.message or spec.error:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "UPDATE scheduled_messages SET message_id = :m, error_message = :e,"
                        " error_code = :c, attempts = 1 WHERE id = :id"
                    ),
                    {
                        "m": seeded.messages[spec.message] if spec.message else None,
                        "e": spec.error,
                        "c": "platform_rejected" if spec.error else None,
                        "id": sid,
                    },
                )
    for spec in SCHEDULED_POSTS:
        assets = [
            await make_asset(engine, workspace_id=wid, purpose="post", height=1350)
            for _ in range(spec.assets)
        ]
        values: dict[str, object] = {}
        if spec.status == "published":
            values["published_at"] = spec.publish_at
        made = await make_scheduled_post(
            engine,
            workspace_id=wid,
            account_ids=[seeded.accounts[a] for a, _ in spec.targets],
            asset_ids=assets,
            status=spec.status,
            caption=spec.caption,
            publish_at=spec.publish_at,
            target_status=spec.targets[0][1],
            target_values=(
                {"error_code": "platform_rejected", "error_message": spec.error}
                if spec.error
                else ({"published_at": spec.publish_at} if spec.status == "published" else None)
            ),
            **values,
        )
        seeded.scheduled_posts[spec.key] = made.id


async def _knowledge(engine: AsyncEngine, seeded: Seeded) -> None:
    """FAQs with their one chunk each, embedded by the fake provider's bag of words (the eval
    embeds queries the same way), and the knowledge gaps."""
    wid = seeded.workspace_id
    for faq in KNOWLEDGE:
        await make_source(
            engine,
            workspace_id=wid,
            question=faq.question,
            body=faq.answer,
            last_ingested_at=ist(9, 1, 10, 0),
            created_by_user_id=seeded.users["owner"],
        )
    for gap in GAPS:
        await make_gap(
            engine,
            workspace_id=wid,
            topic=gap.topic,
            occurrences=gap.occurrences,
            first_seen_at=gap.first_seen_at,
            last_seen_at=gap.last_seen_at,
            example_message_ids=[seeded.messages[k] for k in gap.examples],
            status=gap.status,
            dismissed_at=gap.last_seen_at if gap.status == "dismissed" else None,
        )


# ---------------------------------------------------------------- the answers, from the data
#
# Each mirrors the rule its tool states (a view, a range, spam apart, calendar days), so a case's
# expected number is what the database should give. Ranges are the workspace's calendar days.


def day_start(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=TZ).astimezone(UTC)


def days(since: date, until: date) -> tuple[datetime, datetime]:
    """Local days ``since``..``until`` (both included) as a UTC half-open range."""
    return day_start(since), day_start(until + timedelta(days=1))


def this_week() -> tuple[date, date]:
    monday = TODAY - timedelta(days=TODAY.weekday())
    return monday, monday + timedelta(days=6)


def last_week() -> tuple[date, date]:
    monday, sunday = this_week()
    return monday - timedelta(days=7), sunday - timedelta(days=7)


def this_month() -> tuple[date, date]:
    return TODAY.replace(day=1), TODAY


def last_month() -> tuple[date, date]:
    first = TODAY.replace(day=1)
    end = first - timedelta(days=1)
    return end.replace(day=1), end


def last_days(n: int) -> tuple[date, date]:
    """The last n days as calendar days, today included (analytics)."""
    return TODAY - timedelta(days=n - 1), TODAY


# ---- conversations (search_conversations)


def conversations(
    view: str = "all",
    *,
    platform: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[Conv]:
    def in_view(c: Conv) -> bool:
        if view == "archived":
            return c.status == "archived"
        if c.status != "open":
            return False
        if view == "needs_reply":
            return c.awaiting_reply
        if view == "unread":
            return c.unread > 0
        if view == "leads":
            return (c.lead_score or 0) >= 60
        if view == "closing_soon":
            return c.closing_reminder
        return True

    return [
        c
        for c in CONVERSATIONS
        if in_view(c)
        and (platform is None or c.platform == platform)
        and (start is None or c.last_message_at >= start)
        and (end is None or c.last_message_at < end)
    ]


# ---- comments (get_post_comments, search_comments, sentiment_distribution, comment_topics)


def comments(
    *,
    post: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    account: str | None = None,
    sentiment: str | None = None,
    spam: bool | None = False,
    q: str | None = None,
    replied: bool | None = None,
) -> list[Cmt]:
    """Like CommentQuery: spam False keeps comments not analysed as spam (unanalysed included),
    True spam only, None both; a sentiment matches analysed comments only."""
    found = []
    for p in POSTS:
        if (post is not None and p.key != post) or (account is not None and p.account != account):
            continue
        for c in p.comments:
            if start is not None and c.at < start:
                continue
            if end is not None and c.at >= end:
                continue
            if q is not None and q.casefold() not in c.text.casefold():
                continue
            if replied is not None and (c.reply is not None) != replied:
                continue
            if spam is True and not (c.analysed and c.spam):
                continue
            if spam is False and c.analysed and c.spam:
                continue
            if sentiment is not None and not (
                c.analysed and c.reading is not None and c.reading[0] == sentiment
            ):
                continue
            found.append(c)
    return found


@dataclass(frozen=True)
class Split:
    total: int
    analysed: int
    positive: int
    neutral: int
    negative: int
    spam: int

    def pct(self, sentiment: str) -> float | None:
        clean = self.positive + self.neutral + self.negative
        part = {"positive": self.positive, "neutral": self.neutral, "negative": self.negative}
        return round(part[sentiment] / clean * 100, 1) if clean else None


def sentiment_split(
    *, post: str | None = None, since: date | None = None, until: date | None = None
) -> Split:
    """sentiment_distribution: one post, or the comments made on the calendar days given."""
    if post is not None:
        scope = comments(post=post, spam=None)
    else:
        assert since is not None
        assert until is not None
        start, end = days(since, until)
        scope = comments(start=start, end=end, spam=None)
    readings = [c for c in scope if c.analysed]
    count = Counter(c.reading[0] for c in readings if c.reading is not None and not c.spam)
    return Split(
        total=len(scope),
        analysed=len(readings),
        positive=count["positive"],
        neutral=count["neutral"],
        negative=count["negative"],
        spam=sum(1 for c in readings if c.spam),
    )


def topic_counts(
    *,
    post: str | None = None,
    since: date | None = None,
    until: date | None = None,
    sentiment: str | None = None,
) -> list[tuple[str, int]]:
    """comment_topics: analysed comments that aren't spam, by topic, most frequent first (ties
    A to Z)."""
    if post is not None:
        scope = comments(post=post, spam=None)
    else:
        assert since is not None
        assert until is not None
        start, end = days(since, until)
        scope = comments(start=start, end=end, spam=None)
    count = Counter(
        c.reading[2]
        for c in scope
        if c.analysed
        and c.reading is not None
        and not c.spam
        and c.reading[2] is not None
        and (sentiment is None or c.reading[0] == sentiment)
    )
    return sorted(count.items(), key=lambda kv: (-kv[1], kv[0]))


# ---- posts and analytics


def posts(
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    media_format: str | None = None,
    account: str | None = None,
    q: str | None = None,
) -> list[Post]:
    found = [
        p
        for p in POSTS
        if (start is None or p.posted_at >= start)
        and (end is None or p.posted_at < end)
        and (media_format is None or p.format == media_format)
        and (account is None or p.account == account)
        and (q is None or q.casefold() in p.caption.casefold())
    ]
    return sorted(found, key=lambda p: p.posted_at, reverse=True)


def latest_post(account: str | None = None) -> Post:
    return posts(account=account)[0]


def age_hours(post: Post) -> int:
    return int((NOW - post.posted_at).total_seconds() // 3600)


def lifetime(post: Post) -> dict[str, int]:
    return metrics_at(post, windows_of(post)[-1])


def engagement_rate(values: dict[str, int]) -> float | None:
    reach = values.get("reach")
    parts = [values.get(k) for k in ("likes", "comments", "shares", "saves")]
    if not reach or any(p is None for p in parts):
        return None
    return round(sum(p or 0 for p in parts) / reach * 100, 2)


def value_of(values: dict[str, int], metric: str) -> float | None:
    if metric == "engagement_rate":
        return engagement_rate(values)
    known = values.get(metric)
    return float(known) if known is not None else None


def shown_window(post: Post) -> str:
    """The window a post's own figures are shown at when no age is asked: the latest it has."""
    return windows_of(post)[-1]


@dataclass(frozen=True)
class Compared:
    value: float | None
    median: float | None
    diff_pct: float | None
    size: int


def compare(
    post: Post, metric: str, *, n: int = 10, window: str | None = None, same_format: bool = True
) -> Compared:
    """compare_posts against the account's previous n posts (of the same format by default), at
    the same window."""
    at = window or shown_window(post)
    earlier = [
        p
        for p in posts(account=post.account, media_format=post.format if same_format else None)
        if p.posted_at < post.posted_at
    ][:n]
    values = [
        v
        for p in earlier
        if at in windows_of(p) and (v := value_of(metrics_at(p, at), metric)) is not None
    ]
    mine = value_of(metrics_at(post, at), metric) if at in windows_of(post) else None
    if not values:
        return Compared(mine, None, None, 0)
    median = float(statistics.median(values))
    diff = (
        round((mine - median) / median * 100, 1)
        if mine is not None and len(values) >= 3 and median > 0
        else None
    )
    return Compared(mine, median, diff, len(values))


def top_posts(
    metric: str, since: date, until: date, *, n: int = 5, account: str | None = None
) -> tuple[list[tuple[Post, float]], int]:
    """top_posts at lifetime (each post's latest snapshot): the ranking and the sample size."""
    start, end = days(since, until)
    ranked = [
        (p, v)
        for p in posts(start=start, end=end, account=account)
        if (v := value_of(lifetime(p), metric)) is not None
    ]
    ranked.sort(key=lambda pv: (pv[1], pv[0].posted_at), reverse=True)
    return ranked[:n], len(ranked)


# ---- automations (get_automation_stats)


@dataclass(frozen=True)
class AutomationFigures:
    runs: int
    dms_sent: int
    public_replies: int
    replied_24h: int
    failures: int
    skipped_cooldown: int


def automation_figures(key: str, window_days: int) -> AutomationFigures:
    since = day_start(TODAY - timedelta(days=window_days - 1))
    runs = [r for r in AUTOMATION[key].runs if r.at >= since]

    def dm_sent(r: Run) -> bool:
        if r.dm is None:
            return False
        return (MESSAGE[r.dm][1].status or "sent") == "sent"

    return AutomationFigures(
        runs=len(runs),
        dms_sent=sum(1 for r in runs if dm_sent(r)),
        public_replies=sum(1 for r in runs if r.public_reply),
        replied_24h=sum(1 for r in runs if r.replied_at is not None),
        failures=sum(1 for r in runs if r.result in ("failed", "partial")),
        skipped_cooldown=sum(1 for r in runs if r.result == "skipped_cooldown"),
    )


def active_automations() -> list[AutomationSpec]:
    return [a for a in AUTOMATIONS if a.status == "active"]


# ---- schedules


def pending_messages() -> list[ScheduledMsg]:
    return [s for s in SCHEDULED_MESSAGES if s.status == "scheduled"]


def messages_timed(since: date, until: date) -> list[ScheduledMsg]:
    start, end = days(since, until)
    return [s for s in SCHEDULED_MESSAGES if start <= s.send_at < end and s.status != "canceled"]


def pending_posts() -> list[ScheduledPostSpec]:
    return [s for s in SCHEDULED_POSTS if s.status in ("scheduled", "publishing")]


def posts_timed(since: date, until: date) -> list[ScheduledPostSpec]:
    start, end = days(since, until)
    return [s for s in SCHEDULED_POSTS if start <= s.publish_at < end]


# ---- knowledge


def open_gaps() -> list[GapSpec]:
    since = NOW - timedelta(days=30)
    found = [g for g in GAPS if g.status == "open" and g.last_seen_at >= since]
    return sorted(found, key=lambda g: -g.occurrences)


def numbers_in(values: Iterable[float | int | None]) -> list[float]:
    return [float(v) for v in values if v is not None]


def first(items: Sequence[tuple[Post, float]]) -> float:
    return items[0][1]
