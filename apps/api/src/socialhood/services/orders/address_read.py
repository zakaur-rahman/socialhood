"""Reading a delivery address from a customer's reply (C-218).

    POST …/orders/{order_id}/address/read  {"message_id": "..."}

A WhatsApp cart has no address, so the order's message asks for one (orders.ADDRESS_ASK). When the
customer answers, a member presses Read address: the AI reads that message into the order's
address fields (prompt ``address.v1``), the member checks them and saves them with the order's
edit (PATCH …/orders/{order_id}). Nothing is saved here.

- The message must be the customer's, in the order's conversation, with text.
- 1 credit (address_read, §1.7), reserved before the call and refunded when it fails (TR-AI-09):
  quota_exceeded leaves the route's credits gate as the §4.7 402; 503 when the model can't answer.
- A part the message doesn't give stays empty (the model is told never to guess), and every part is
  cut to the order address's limits.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.ai import prompts
from socialhood.ai.metering import QuotaExceeded, metered
from socialhood.ai.provider import AIError, Turn
from socialhood.ai.registry import get_provider
from socialhood.errors import ApiError, FieldError
from socialhood.models.billing import AiFeature
from socialhood.models.inbox import Message
from socialhood.models.orders import Order
from socialhood.observability.logging import get_logger
from socialhood.schemas.orders import AddressIn, AddressOut, AddressReading
from socialhood.services.suggestions.drafting import load_brand
from socialhood.settings import get_settings

log = get_logger(__name__)

FEATURE = AiFeature.ADDRESS_READ.value
MAX_OUTPUT_TOKENS = 400
TEMPERATURE = 0.0
TIMEOUT_S = 12.0

NOT_THEIRS = "Choose a message the customer sent in this order's conversation."
NO_CREDITS = "Your AI credits are used up until they reset."
AI_UNAVAILABLE = "The AI couldn't read the address just now. Try again, or type it in."


class AddressGuess(BaseModel):
    found: bool
    name: str | None = None
    phone: str | None = None
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    country: str | None = None


def cleaned(guess: AddressGuess) -> AddressOut:
    """Each part trimmed and cut to the order address's limits (schemas/orders.AddressIn)."""
    parts: dict[str, str | None] = {}
    for name, info in AddressIn.model_fields.items():
        value = getattr(guess, name)
        limit = next((m.max_length for m in info.metadata if hasattr(m, "max_length")), None)
        text = " ".join(str(value).split()) if value else ""
        parts[name] = (text[:limit] if limit else text) or None
    return AddressOut(**parts)


async def read(
    session: AsyncSession,
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    workspace_id: uuid.UUID,
    order: Order,
    message_id: uuid.UUID,
) -> AddressReading:
    msg = await session.get(Message, message_id)
    if (
        msg is None
        or msg.conversation_id != order.conversation_id
        or msg.direction != "inbound"
        or not (msg.text or "").strip()
    ):
        raise ApiError("validation_error", errors=[FieldError("message_id", NOT_THEIRS)])
    brand = await load_brand(session)
    system = prompts.load("address").render(business_name=brand.business_name)
    text = msg.text or ""
    await session.commit()  # no transaction stays open while the model runs
    settings = get_settings()
    try:
        async with metered(sessionmaker, workspace_id=workspace_id, feature=FEATURE) as meter:
            result = await get_provider().generate_json(
                task="address",
                schema=AddressGuess,
                system=system,
                contents=[Turn("user", f"MESSAGE:\n{text}")],
                model=settings.ai_model_reply,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                temperature=TEMPERATURE,
                timeout_s=TIMEOUT_S,
            )
            meter.record(result)
    except QuotaExceeded as error:
        raise ApiError("quota_exceeded", NO_CREDITS) from error
    except AIError as error:
        log.warning("address_read_failed", error_code=error.code)
        raise ApiError("service_unavailable", AI_UNAVAILABLE) from error
    guess = result.value
    address = cleaned(guess) if guess.found else AddressOut()
    found = guess.found and any(v for v in address.model_dump().values())
    return AddressReading(found=found, address=address)
