"""FR-INB-01 and T3.5's done-when: search returns within 500 ms at 100k messages per workspace.

Seeds 5,000 conversations with 20 messages each in one workspace (INSERT ... SELECT over
generate_series), then times searches through the API: rare and common words, prefixes, names,
usernames, Hindi text, and search within a view.
"""

from __future__ import annotations

import statistics
import time
import uuid

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.api import Clerk, sign_in
from tests.support.inbox import make_account

# A wall-clock budget: timed beside other tests (pytest -n) it measures the machine's load, not
# the query. CI runs it alone after the parallel run (pytest -m serial).
pytestmark = pytest.mark.serial

CONVERSATIONS = 5_000
PER_CONVERSATION = 20
BUDGET_MS = 500

PHRASES = [
    "Do you ship to Pune?",
    "Is the linen shirt available in M?",
    "What is the price of the",
    "Can I get a discount on the",
    "My order has not arrived yet, it has been nine days",
    "Thanks, got it!",
    "Do you have cash on delivery for the",
    "How long does delivery to Dubai take?",
    "Can you hold one for me?",
    "Please share the size chart for the",
    "Yes! It is in stock. Want me to reserve one?",
    "We ship across India in 3 to 5 days.",
    "क्या आप दिल्ली में डिलीवर करते हैं?",
    "Is this available in black?",
    "I want to return the",
    "Sent the payment link for the",
]
PRODUCTS = [
    "Aria dress",
    "linen shirt",
    "denim jacket",
    "silk scarf",
    "canvas tote",
    "leather wallet",
    "cotton kurta",
    "wool sweater",
]
FIRST = ["Priya", "Rohan", "Aarav", "Sara", "Kabir", "Meera", "Ishaan", "Anaya"]
LAST = ["Nair", "Shah", "Mehta", "Ali", "Khan", "Rao", "Das", "Iyer", "Kapoor", "Singh"]


async def seed(engine: AsyncEngine, wid: str, account_id: uuid.UUID) -> None:
    params = {
        "w": wid,
        "a": account_id,
        "n": CONVERSATIONS,
        "m": PER_CONVERSATION - 1,
        "first": FIRST,
        "last": LAST,
        "phrases": PHRASES,
        "products": PRODUCTS,
    }
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO contacts (workspace_id, social_account_id, platform_user_id,"
                " username, display_name, first_seen_at)"
                " SELECT :w, :a, 'igsid_' || g, 'shopper_' || g,"
                " (CAST(:first AS text[]))[1 + g % cardinality(CAST(:first AS text[]))] || ' '"
                " || (CAST(:last AS text[]))[1 + (g / 8) % cardinality(CAST(:last AS text[]))],"
                " now() - interval '30 days'"
                " FROM generate_series(1, :n) g"
            ),
            params,
        )
        await conn.execute(
            text(
                "INSERT INTO conversations (workspace_id, social_account_id, contact_id, platform,"
                " status, last_message_at, last_inbound_at, last_message_preview,"
                " last_message_direction, last_message_source, last_message_kind, unread_count,"
                " awaiting_reply)"
                " SELECT :w, :a, c.id, 'instagram',"
                " CASE WHEN g % 10 = 0 THEN 'archived' ELSE 'open' END,"
                " now() - g * interval '1 minute', now() - g * interval '1 minute',"
                " 'Latest message', 'inbound', 'customer', 'text', g % 3, g % 2 = 0"
                " FROM (SELECT id, substr(platform_user_id, 7)::int AS g FROM contacts"
                "       WHERE workspace_id = :w) c"
            ),
            params,
        )
        await conn.execute(
            text(
                "INSERT INTO messages (workspace_id, conversation_id, social_account_id,"
                " direction, source, kind, text, occurred_at, platform_message_id, status)"
                " SELECT :w, conv.id, :a,"
                " CASE WHEN m % 2 = 0 THEN 'inbound' ELSE 'outbound' END,"
                " CASE WHEN m % 2 = 0 THEN 'customer' ELSE 'human' END,"
                " 'text',"
                " (CAST(:phrases AS text[]))"
                "   [1 + (g * 7 + m) % cardinality(CAST(:phrases AS text[]))] || ' '"
                " || (CAST(:products AS text[]))"
                "   [1 + (g + m) % cardinality(CAST(:products AS text[]))]"
                " || ' #' || (g * 20 + m)"
                " || CASE WHEN g % 1000 = 123 AND m = 3 THEN ' zanzibar' ELSE '' END,"
                " conv.last_message_at - m * interval '1 minute',"
                " 'mid_' || g || '_' || m,"
                " CASE WHEN m % 2 = 0 THEN 'received' ELSE 'sent' END"
                " FROM (SELECT c.id, c.last_message_at, substr(ct.platform_user_id, 7)::int AS g"
                "       FROM conversations c JOIN contacts ct ON ct.id = c.contact_id"
                "       WHERE c.workspace_id = :w) conv"
                " CROSS JOIN generate_series(0, :m) m"
            ),
            params,
        )
    async with engine.begin() as conn:
        count = await conn.scalar(
            text("SELECT count(*) FROM messages WHERE workspace_id = :w"), {"w": wid}
        )
        assert count == CONVERSATIONS * PER_CONVERSATION
        await conn.execute(text("ANALYZE contacts, conversations, messages"))


async def test_search_is_under_500_ms_at_100k_messages(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    account_id = await make_account(engine, wid)
    started = time.perf_counter()
    await seed(engine, wid, account_id)
    seeded_s = time.perf_counter() - started

    async def search(**params: str) -> tuple[float, dict[str, object]]:
        headers = clerk.headers(clerk_id)
        began = time.perf_counter()
        response = await client.get(f"/v1/w/{wid}/conversations", params=params, headers=headers)
        elapsed_ms = (time.perf_counter() - began) * 1000
        assert response.status_code == 200, response.text
        return elapsed_ms, response.json()

    queries: list[dict[str, str]] = [
        {"q": "zanzibar"},  # 5 messages
        {"q": "ship"},
        {"q": "pune"},
        {"q": "linen shirt"},
        {"q": "a"},  # the broadest prefix
        {"q": "#12345"},
        {"q": "priya"},  # names
        {"q": "@shopper_4242"},
        {"q": "Kapoor"},
        {"q": "दिल्ली"},
        {"q": "nothing matches this"},
        {"q": "ship", "view": "unread"},
        {"q": "zanzibar", "view": "archived"},
        {"q": "dress", "view": "needs_reply", "limit": "100"},
    ]
    # Each search runs three times: the first is cold (no cached plan or pages), the median is
    # what the budget applies to, so a busy test machine does not fail the run on one outlier.
    timings: dict[str, list[float]] = {}
    for params in queries:
        runs = [await search(**params) for _ in range(3)]
        label = " ".join(f"{k}={v}" for k, v in params.items())
        timings[label.encode("ascii", "backslashreplace").decode()] = [ms for ms, _ in runs]
        body = runs[0][1]
        if params["q"] == "zanzibar":
            # One message in each of conversations 123, 1123, 2123, 3123 and 4123 (all open).
            assert len(body["items"]) == (0 if "view" in params else 5)  # type: ignore[arg-type]
        if params["q"] == "@shopper_4242":
            assert len(body["items"]) == 1  # type: ignore[arg-type]

    report = "\n".join(
        f"  {name}: first {runs[0]:.1f} ms, median {statistics.median(runs):.1f} ms"
        for name, runs in timings.items()
    )
    print(f"\nSeeded {CONVERSATIONS * PER_CONVERSATION} messages in {seeded_s:.1f} s\n{report}")
    slow = {name: runs for name, runs in timings.items() if statistics.median(runs) >= BUDGET_MS}
    assert not slow, f"searches over {BUDGET_MS} ms: {slow}"
