"""A message to the customer about an order's new status (GR-32 follow-up, C-125).

When a member marks an order paid, shipped, cancelled or refunded they can ask for a message to
the customer on the order's conversation. The status change is never held up by the message: it
is made first, and the answer says whether the message went and, if not, why.

- **Inside the messaging window** the message goes as text (the default wording below, or the
  member's own).
- **Outside it on WhatsApp** only an approved template can go, and only a *utility* one (an order
  update is not marketing, so no marketing consent is involved). The member names the template;
  its variables are filled in this order: the customer's first name, the order number, the order
  total, the new status in words. A template with more variables than that can't be used. With no
  template chosen the message is not sent, and the answer says what to do.
- **Outside it on Instagram or Messenger** nothing can be sent (Human Agent applies for a
  member's message, as everywhere: ``queue_outbound`` decides).
- An order with no conversation, or one whose account needs reconnecting, says so.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError
from socialhood.models.inbox import Contact, Conversation
from socialhood.models.orders import Order
from socialhood.platforms.base import OutboundTemplate
from socialhood.platforms.deps import PlatformDeps
from socialhood.repositories import inbox
from socialhood.repositories import social_accounts as accounts
from socialhood.schemas.orders import NoticeIn, NoticeOut
from socialhood.services import sending, whatsapp_templates
from socialhood.services.automations import actions
from socialhood.services.catalogue import money
from socialhood.services.orders import orders

# The variables a template can carry: first name, order number, total, status in words.
MAX_VARIABLES = 4
COPY = {
    "no_conversation": "This order has no conversation, so there is nobody to message.",
    "no_template": (
        "The 24-hour window has closed. WhatsApp only allows an approved template now. "
        "Choose a utility template to send this update."
    ),
    "window_closed": (
        "The messaging window has closed. {channel} only allows messages for 24 hours after the "
        "customer writes."
    ),
    "not_utility": "Only an approved utility template can carry an order update.",
    "too_many": "That template needs more details than an order update can fill in. "
    f"Choose one with up to {MAX_VARIABLES} variables.",
    "not_found": "That template isn't approved on this number. Choose another.",
}
CHANNEL = {"instagram": "Instagram", "facebook": "Messenger", "whatsapp": "WhatsApp"}


def default_text(order: Order, event: str, *, amount_minor: int | None = None) -> str:
    """The message when the member wrote none. ``event`` is paid, partially_paid, fulfilled,
    cancelled or refunded."""
    number = f"order #{order.number}"
    cur = order.currency
    match event:
        case "paid":
            return (
                f"Thanks, we've got your payment for {number} "
                f"({money.label(order.total_minor, cur)})."
            )
        case "partially_paid":
            got = money.label(amount_minor or order.amount_paid_minor, cur)
            left = money.label(max(0, order.total_minor - order.amount_paid_minor), cur)
            return f"We've received {got} for {number}. {left} is still to pay."
        case "fulfilled":
            note = f" {order.fulfilment_note}" if order.fulfilment_note else ""
            return f"Good news: {number} is on its way.{note}"
        case "cancelled":
            return f"{number.capitalize()} has been cancelled."
        case "refunded":
            got = money.label(amount_minor or order.amount_refunded_minor, cur)
            return (
                f"We've refunded {got} for {number}. "
                "It can take a few days to show in your account."
            )
        case _:
            return f"There's an update on {number}."


def _variables(order: Order, contact: Contact | None, status_words: str) -> list[str]:
    first = ((contact.display_name or "").split() or ["there"])[0] if contact else "there"
    return [first, f"#{order.number}", money.label(order.total_minor, order.currency), status_words]


async def send(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    order: Order,
    *,
    event: str,
    notice: NoticeIn,
    user_id: uuid.UUID,
    amount_minor: int | None = None,
    now: datetime,
) -> NoticeOut:
    """Send the update. Never raises for a message that can't go: the answer says why."""
    if order.conversation_id is None:
        return NoticeOut(sent=False, reason=COPY["no_conversation"])
    conv = await inbox.get_conversation(session, order.conversation_id)
    if conv is None:
        return NoticeOut(sent=False, reason=COPY["no_conversation"])
    text = (notice.message or "").strip() or default_text(order, event, amount_minor=amount_minor)
    try:
        async with session.begin_nested():
            await sending.queue_outbound(
                session,
                conv,
                source="human",
                client_id=uuid.uuid4(),
                text=text,
                sent_by_user_id=user_id,
                deps=deps,
                now=now,
            )
        return NoticeOut(sent=True)
    except ApiError as error:
        if error.code != "reply_window_closed":
            return NoticeOut(sent=False, reason=actions.api_error_reason(error))
    # The window has closed.
    if conv.platform != "whatsapp":
        return NoticeOut(
            sent=False,
            reason=COPY["window_closed"].format(channel=CHANNEL.get(conv.platform, "This channel")),
        )
    if not notice.template_name or not notice.template_language:
        return NoticeOut(sent=False, reason=COPY["no_template"])
    return await _template(
        session,
        redis,
        deps,
        order,
        conv_account=conv.social_account_id,
        conv=conv,
        event=event,
        notice=notice,
        user_id=user_id,
        now=now,
    )


async def _template(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    order: Order,
    *,
    conv_account: uuid.UUID,
    conv: Conversation,
    event: str,
    notice: NoticeIn,
    user_id: uuid.UUID,
    now: datetime,
) -> NoticeOut:
    acct = await accounts.get(session, conv_account)
    if acct is None:
        return NoticeOut(sent=False, reason=COPY["no_conversation"])
    try:
        approved = await whatsapp_templates.approved_templates(session, redis, deps, acct)
    except ApiError as error:
        return NoticeOut(sent=False, reason=actions.api_error_reason(error))
    template = next(
        (
            t
            for t in approved
            if t.name == notice.template_name and t.language == notice.template_language
        ),
        None,
    )
    if template is None:
        return NoticeOut(sent=False, reason=COPY["not_found"])
    if template.category != "utility":
        return NoticeOut(sent=False, reason=COPY["not_utility"])
    if template.param_count > MAX_VARIABLES:
        return NoticeOut(sent=False, reason=COPY["too_many"])
    contact = await orders.session_contact(session, order)
    words = orders.STATUS_WORDS.get(order.status, order.status)
    params = _variables(order, contact, words)[: template.param_count]
    try:
        async with session.begin_nested():
            await sending.queue_outbound(
                session,
                conv,
                source="human",
                client_id=uuid.uuid4(),
                template=OutboundTemplate(
                    name=template.name, language=template.language, params=tuple(params)
                ),
                sent_by_user_id=user_id,
                deps=deps,
                now=now,
            )
    except ApiError as error:
        return NoticeOut(sent=False, reason=actions.api_error_reason(error))
    return NoticeOut(sent=True)
