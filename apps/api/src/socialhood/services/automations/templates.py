"""The template gallery (FR-AUT-12, UX-SCR-11), defined in code.

Each template fills the trigger, keywords, messages and settings of a new draft, which the user
then edits; the draft stores the template's key. Link buttons start with the address "https://"
so the editor shows where the link goes, and activation asks for it (FR-AUT-13).

Tap first (FR-AUT-21) is on for the comment templates that send a message; every draft gets the
default opening and follow line (FR-AUT-22), and the link template has the nudge on.
"""

from __future__ import annotations

from dataclasses import dataclass

from socialhood.schemas.automations import (
    ActionName,
    AutomationTemplate,
    AutomationTemplateList,
    PostScopeName,
    TemplateCategory,
    TriggerName,
)

LINK_PLACEHOLDER = "https://"
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
)

BY_KEY: dict[str, Template] = {t.key: t for t in TEMPLATES}


def gallery() -> AutomationTemplateList:
    return AutomationTemplateList(items=[t.summary() for t in TEMPLATES])


def find(key: str) -> Template | None:
    return BY_KEY.get(key)
