"""The template gallery (FR-AUT-12, UX-SCR-11), defined in code.

Each template fills the trigger, keywords, messages and settings of a new draft, which the user
then edits; the draft stores the template's key. Link buttons start with the address "https://"
so the editor shows where the link goes, and activation asks for it (FR-AUT-13).

Tap first (FR-AUT-21) is on for the comment templates that send a message; every draft gets the
default opening and follow line (FR-AUT-22), and the link template has the nudge on.

A template can carry a flow (GR-16, C-099): the draft is then created saved as a flow, version 1,
and the message settings are not used. Every flow template stays within the Free plan's step cap
(``flow_steps``, 5, PD-5 pending), keeps its questions to an email or a phone (saved to the
contact, so no custom field has to exist), and leaves its link as "https://" and its prices and
codes in [brackets], to be filled before activation.

``PLACEHOLDERS`` is the one list of those bracket tokens. Activation refuses a flow or a message
whose send text still holds one (``unfilled``, used by validation.py and flows.py), with
"Replace [price] with your price." on the step. Only the tokens listed count, so other brackets in
a user's text ("[Free shipping]", "[1]") are left alone. The web editor mirrors the list
(lib/automations/flow.ts, PLACEHOLDERS): add a token in both places and use it in a template.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from socialhood.schemas.automations import (
    ActionName,
    AutomationTemplate,
    AutomationTemplateList,
    PostScopeName,
    TemplateCategory,
    TriggerName,
)
from socialhood.schemas.flows import (
    ActionStep,
    AskStep,
    FlowButton,
    FlowDefinition,
    NotifyTeam,
    QuickReply,
    SendStep,
)

LINK_PLACEHOLDER = "https://"
# The bracket tokens the templates leave for the user to fill: token -> what goes there.
PLACEHOLDERS: dict[str, str] = {"[price]": "your price", "[code]": "your code"}
_PLACEHOLDER = re.compile("|".join(re.escape(token) for token in PLACEHOLDERS), re.IGNORECASE)


def unfilled(text: str) -> list[str]:
    """The placeholder tokens still in ``text`` (lower case, each once, in order of appearance)."""
    return list(dict.fromkeys(found.lower() for found in _PLACEHOLDER.findall(text or "")))


def unfilled_copy(token: str) -> str:
    """The error for a token left in a message, e.g. "Replace [price] with your price."."""
    return f"Replace {token} with {PLACEHOLDERS[token]}."


# FR-AUT-21 and FR-AUT-22 defaults. The opening asks for a reply too: quick replies are not shown
# on desktop, and an opening Instagram refuses with its quick reply goes out as text.
OPENING_TEXT = (
    "Hi {first_name|there}! Tap the button below, or just reply here, and I'll send it right over "
    "\N{WHITE DOWN POINTING BACKHAND INDEX}"
)
OPENING_BUTTON = "Send me the link"
FOLLOW_NUDGE_TEXT = "Enjoying this? Follow us for more like it."


@dataclass(frozen=True)
class Button:
    title: str
    url: str = LINK_PLACEHOLDER


@dataclass(frozen=True)
class Template:
    key: str
    name: str
    outcome: str
    category: TemplateCategory
    icon: str  # a lucide icon name
    trigger: TriggerName
    action: ActionName
    keywords: tuple[str, ...] = ()
    message_text: str | None = None
    message_buttons: tuple[Button, ...] = ()
    ai_instructions: str | None = None
    public_reply_texts: tuple[str, ...] = ()
    post_scope: PostScopeName = "all"
    cooldown_hours: int = 24
    confirm_first: bool = False  # FR-AUT-21
    follow_nudge: bool = False  # FR-AUT-22
    story_heart: bool = False  # GR-06
    flow: FlowDefinition | None = None  # GR-16: the draft is created saved as this flow

    @property
    def requires_paid_plan(self) -> bool:
        return self.action == "ai_reply"  # ai_reply_automations (§1.7)

    def summary(self) -> AutomationTemplate:
        return AutomationTemplate(
            key=self.key,
            name=self.name,
            outcome=self.outcome,
            category=self.category,
            icon=self.icon,
            trigger=self.trigger,
            action=self.action,
            requires_paid_plan=self.requires_paid_plan,
            steps=len(self.flow.steps) if self.flow else 0,
        )


def _flow(start: str, *steps: SendStep | AskStep | ActionStep) -> FlowDefinition:
    return FlowDefinition(start=start, steps=list(steps))


STORY_GIVEAWAY_FLOW = _flow(
    "thanks",
    SendStep(
        id="thanks",
        text="Thanks for sharing us, {first_name|friend}! You're in the draw.",
        next="when",
    ),
    SendStep(id="when", text="Winners are announced in our stories. Good luck!"),
)

LEAD_MAGNET_FLOW = _flow(
    "email",
    AskStep(
        id="email",
        text="Hi {first_name|there}! Reply with your email address and I'll send the guide.",
        expect="email",
        retry_text="That doesn't look like an email address. Could you type it again?",
        next="guide",
    ),
    SendStep(
        id="guide",
        text="Thanks! Here's your guide.",
        buttons=[FlowButton(title="Get the PDF", url=LINK_PLACEHOLDER)],
    ),
)

PRICE_BY_OPTION_FLOW = _flow(
    "which",
    SendStep(
        id="which",
        text="Hi {first_name|there}! Which size would you like the price for?",
        quick_replies=[
            QuickReply(title="Small", next="price_small"),
            QuickReply(title="Medium", next="price_medium"),
            QuickReply(title="Large", next="price_large"),
        ],
    ),
    SendStep(id="price_small", text="The small one is [price]. Reply here if you'd like to order."),
    SendStep(
        id="price_medium", text="The medium one is [price]. Reply here if you'd like to order."
    ),
    SendStep(id="price_large", text="The large one is [price]. Reply here if you'd like to order."),
)

CALL_REQUEST_FLOW = _flow(
    "phone",
    AskStep(
        id="phone",
        text="Hi {first_name|there}! What's the best number to call you on?",
        expect="phone",
        retry_text="That doesn't look like a phone number. Could you type it again?",
        confirm_text="Thanks! We'll call you soon.",
        next="tell_team",
    ),
    ActionStep(
        id="tell_team",
        action=NotifyTeam(note="Someone asked for a call. Their number is on their contact."),
    ),
)

COUPON_FLOW = _flow(
    "code",
    SendStep(
        id="code",
        text="Welcome, {first_name|there}! Your code is [code]. Use it at checkout.",
        buttons=[FlowButton(title="Shop now", url=LINK_PLACEHOLDER)],
    ),
)


TEMPLATES: tuple[Template, ...] = (
    Template(
        key="send_link",
        name="Send a link to commenters",
        outcome="Send your link to everyone who comments LINK",
        category="grow",
        icon="link",
        trigger="comment_keyword",
        action="send_message",
        keywords=("link",),
        message_text="Hi {first_name|there}! Here's the link you asked for.",
        message_buttons=(Button("Open link"),),
        public_reply_texts=(
            "Sent you a DM!",
            "Check your DMs, {first_name|friend}!",
            "Just sent it to your inbox.",
        ),
        confirm_first=True,
        follow_nudge=True,
    ),
    Template(
        key="giveaway",
        name="Giveaway replies",
        outcome="Reply to every comment on your giveaway post and DM the rules",
        category="grow",
        icon="gift",
        trigger="comment_any",
        action="send_message",
        post_scope="selected",
        message_text=(
            "Thanks for entering, {first_name|there}! Here are the rules:\n"
            "1. Follow our account\n2. Tag two friends in the comments\n"
            "Winners are announced in our stories."
        ),
        public_reply_texts=(
            "You're in! Good luck.",
            "Entry counted, {first_name|friend}! The rules are in your DMs.",
            "Good luck! Check your DMs for the rules.",
        ),
        confirm_first=True,
    ),
    Template(
        key="price_on_request",
        name="Price on request",
        outcome="Answer PRICE comments with the price, in a DM",
        category="sell",
        icon="tag",
        trigger="comment_keyword",
        action="ai_reply",
        keywords=("price",),
        ai_instructions=(
            "Tell them the price of the product in this post, from the catalogue or the "
            "knowledge base. Keep it short and friendly, and ask if they'd like to order."
        ),
        public_reply_texts=(
            "Sent you the price in a DM!",
            "Check your DMs, {first_name|friend}!",
        ),
    ),
    Template(
        key="catalogue_by_dm",
        name="Catalogue by DM",
        outcome="Send your catalogue to anyone who DMs CATALOGUE",
        category="sell",
        icon="shopping-bag",
        trigger="dm_keyword",
        action="send_message",
        keywords=("catalogue", "catalog"),
        message_text="Hi {first_name|there}! Here's our latest catalogue.",
        message_buttons=(Button("View catalogue"),),
    ),
    Template(
        key="answer_faqs",
        name="Answer FAQs",
        outcome="Answer questions about shipping, returns and sizes with AI",
        category="support",
        icon="circle-help",
        trigger="dm_keyword",
        action="ai_reply",
        keywords=("shipping", "delivery", "returns", "size"),
        ai_instructions=(
            "Answer the question from the knowledge base in two or three sentences. If the "
            "answer isn't there, say someone from the team will reply soon."
        ),
    ),
    Template(
        key="book_a_call",
        name="Book a call",
        outcome="Send your booking link to anyone who DMs BOOK",
        category="sell",
        icon="calendar",
        trigger="dm_keyword",
        action="send_message",
        keywords=("book",),
        message_text="Hi {first_name|there}! Pick a time that suits you and we'll call you.",
        message_buttons=(Button("Book a call"),),
    ),
    Template(
        key="story_reply_link",
        name="Reply to story, send the link",
        outcome="Send your link to anyone who replies LINK to your story",
        category="grow",
        icon="message-circle",
        trigger="story_reply",
        action="send_message",
        keywords=("link",),
        message_text="Hi {first_name|there}! Thanks for replying. Here's the link you asked for.",
        message_buttons=(Button("Open link"),),
    ),
    Template(
        key="thank_story_mentions",
        name="Thank story mentions",
        outcome="Thank everyone who mentions you in their story",
        category="grow",
        icon="at-sign",
        trigger="story_mention",
        action="send_message",
        message_text=(
            "Thanks for the mention, {first_name|friend}! It made our day. "
            "Here's a little something for you."
        ),
        message_buttons=(Button("Claim your reward"),),
    ),
    Template(
        key="welcome_new_contacts",
        name="Welcome new contacts",
        outcome="Greet everyone the first time they DM you",
        category="grow",
        icon="hand",
        trigger="first_message",
        action="send_message",
        message_text=(
            "Hi {first_name|there}! Thanks for getting in touch. We'll reply as soon as we can."
        ),
    ),
    Template(
        key="default_reply_when_ai_off",
        name="Default reply",
        outcome="Answer DMs nothing else answers, while AI replies are off",
        category="support",
        icon="message-square-reply",
        trigger="default_reply",
        action="send_message",
        message_text=(
            "Hi {first_name|there}! Thanks for your message. A person will get back to you soon."
        ),
        cooldown_hours=12,
    ),
    Template(
        key="story_giveaway",
        name="Story giveaway",
        outcome="Thank everyone who mentions you in their story and enter them in the draw",
        category="grow",
        icon="gift",
        trigger="story_mention",
        action="send_message",
        confirm_first=False,
        flow=STORY_GIVEAWAY_FLOW,
    ),
    Template(
        key="lead_magnet",
        name="Lead magnet",
        outcome="Ask commenters for their email, then send your PDF",
        category="grow",
        icon="book-open",
        trigger="comment_keyword",
        action="send_message",
        keywords=("guide",),
        public_reply_texts=(
            "Sent you a DM!",
            "Check your DMs, {first_name|friend}!",
        ),
        confirm_first=False,
        flow=LEAD_MAGNET_FLOW,
    ),
    Template(
        key="price_by_option",
        name="Price by option",
        outcome="Ask which size a PRICE commenter wants, then send that price",
        category="sell",
        icon="tag",
        trigger="comment_keyword",
        action="send_message",
        keywords=("price",),
        public_reply_texts=(
            "Sent you a DM!",
            "Check your DMs, {first_name|friend}!",
        ),
        confirm_first=False,
        flow=PRICE_BY_OPTION_FLOW,
    ),
    Template(
        key="call_request",
        name="Call requests",
        outcome="Ask for a phone number when someone messages CALL, and tell your team",
        category="sell",
        icon="calendar",
        trigger="dm_keyword",
        action="send_message",
        keywords=("call",),
        confirm_first=False,
        flow=CALL_REQUEST_FLOW,
    ),
    Template(
        key="entry_link_coupon",
        name="Coupon from a link",
        outcome="Send a coupon code to everyone who opens your entry link",
        category="sell",
        icon="shopping-bag",
        trigger="entry_link",
        action="send_message",
        confirm_first=False,
        flow=COUPON_FLOW,
    ),
)

BY_KEY: dict[str, Template] = {t.key: t for t in TEMPLATES}


def gallery() -> AutomationTemplateList:
    return AutomationTemplateList(items=[t.summary() for t in TEMPLATES])


def find(key: str) -> Template | None:
    return BY_KEY.get(key)
