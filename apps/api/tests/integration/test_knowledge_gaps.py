"""T5.10: questions the AI couldn't answer (FR-KB-06, TR-AI-12, F-17). Done when: "Do you ship to
Dubai?" and "shipping to UAE?" merge into one gap; answering removes it. Plus dismiss and reopen,
counting each message once, the 30-day list with examples, and Home's count.

How the two questions merge: suggest.v1 asks the model for a 2-4 word label and gives "shipping to
uae" as its example, so both questions arrive labelled alike and meet by exact or trigram match.
Trigram similarity alone does not merge the labels "shipping to dubai" and "shipping to uae"
(0.55 < 0.6); see docs/CONFLICTS.md for the proposed rule.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from socialhood.db.engine import make_sessionmaker
from socialhood.db.tenancy import workspace_scope
from socialhood.services.knowledge.gaps import normalize_topic, open_topics, record_gap
from tests.support.ai import make_gap
from tests.support.api import Clerk
from tests.support.automation_api import Ws, workspace
from tests.support.inbox import make_thread
from tests.support.ingest import rows

NOW = datetime.now(UTC)


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk, queue: None) -> Ws:
    return await workspace(client, clerk)


@pytest.fixture
def maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return make_sessionmaker(engine)


async def asked(engine: AsyncEngine, ws: Ws, *texts: str) -> list[uuid.UUID]:
    """Customer messages (one conversation), oldest first."""
    thread = await make_thread(engine, workspace_id=ws.wid, account_id=ws.account_id, texts=texts)
    return thread.message_ids


async def record(
    maker: async_sessionmaker[AsyncSession],
    ws: Ws,
    topic: str,
    message_id: uuid.UUID,
    now: datetime | None = None,
) -> uuid.UUID:
    """What the suggestion job does with a can_answer = false suggestion."""
    with workspace_scope(uuid.UUID(ws.wid)):
        async with maker() as session:
            gap = await record_gap(
                session, missing_topic=topic, message_id=message_id, now=now or datetime.now(UTC)
            )
            await session.commit()
            return gap.id


async def gap_rows(engine: AsyncEngine) -> list[dict[str, object]]:
    return await rows(
        engine,
        "SELECT id, topic, topic_normalized, status, occurrences, example_message_ids,"
        " resolved_source_id, dismissed_at FROM knowledge_gaps ORDER BY first_seen_at, id",
    )


@pytest.mark.parametrize(
    ("label", "normalized"),
    [
        ("Shipping to UAE?", "shipping to uae"),
        ("  shipping   to the U.A.E. ", "shipping to the uae"),
        ("Don't you do COD?!", "dont you do cod"),
        ("cash-on-delivery", "cash on delivery"),
        ("Größe / Sizes", "grösse sizes"),
        ("???", ""),
    ],
)
def test_topics_are_normalised(label: str, normalized: str) -> None:
    assert normalize_topic(label) == normalized


async def test_do_you_ship_to_dubai_and_shipping_to_uae_are_one_gap(
    ws: Ws, engine: AsyncEngine, maker: async_sessionmaker[AsyncSession]
) -> None:
    dubai, uae, the_uae = await asked(
        engine, ws, "Do you ship to Dubai?", "shipping to UAE?", "Can you send a cake to the UAE?"
    )

    # The model's labels (suggest.v1's own example for a Dubai question is "shipping to uae").
    first = await record(maker, ws, "shipping to uae", dubai)
    assert await record(maker, ws, "Shipping to UAE", uae) == first  # exact after normalising
    assert await record(maker, ws, "shipping to the UAE", the_uae) == first  # trigram 0.84

    [gap] = await gap_rows(engine)
    assert (gap["topic"], gap["status"], gap["occurrences"]) == ("shipping to uae", "open", 3)
    assert gap["example_message_ids"] == [the_uae, uae, dubai]  # newest first
    listed = await ws.ok("GET", "/knowledge-gaps")
    [item] = listed["items"]
    assert (item["topic"], item["occurrences"]) == ("shipping to uae", 3)
    assert [e["text"] for e in item["examples"]] == [
        "Can you send a cake to the UAE?",
        "shipping to UAE?",
        "Do you ship to Dubai?",
    ]


async def test_trigram_similarity_alone_is_the_merge_rule(
    ws: Ws, engine: AsyncEngine, maker: async_sessionmaker[AsyncSession]
) -> None:
    """TR-AI-12 as written: exact or pg_trgm similarity >= 0.6. It keeps "shipping to dubai"
    apart from "shipping to uae" (0.55) and joins "uae shipping" (0.81) and, wrongly, "shipping
    to usa" (0.68). Recorded in docs/CONFLICTS.md with the proposed fix."""
    m = await asked(engine, ws, "a", "b", "c", "d", "e")

    uae = await record(maker, ws, "shipping to uae", m[0])
    dubai = await record(maker, ws, "shipping to dubai", m[1])
    assert await record(maker, ws, "UAE shipping", m[2]) == uae
    assert await record(maker, ws, "shipping to usa", m[3]) == uae
    assert await record(maker, ws, "return policy", m[4]) not in (uae, dubai)

    assert [g["occurrences"] for g in await gap_rows(engine)] == [3, 1, 1]


async def test_a_message_counts_once_and_five_examples_are_kept(
    ws: Ws, engine: AsyncEngine, maker: async_sessionmaker[AsyncSession]
) -> None:
    messages = await asked(engine, ws, *(f"Is there a vegan option {n}?" for n in range(7)))

    gap_id = await record(maker, ws, "vegan cakes", messages[0])
    await record(maker, ws, "vegan cakes", messages[0])  # a regenerated suggestion
    for message_id in messages[1:]:
        await record(maker, ws, "Vegan cakes", message_id)

    [gap] = await gap_rows(engine)
    assert gap["id"] == gap_id
    assert gap["occurrences"] == 7
    assert gap["example_message_ids"] == list(reversed(messages))[:5]
    [item] = (await ws.ok("GET", "/knowledge-gaps"))["items"]
    assert [e["text"] for e in item["examples"]] == [
        "Is there a vegan option 6?",
        "Is there a vegan option 5?",
        "Is there a vegan option 4?",
    ]
    assert item["examples"][0]["message_id"] == str(messages[6])


async def test_the_list_is_open_gaps_of_30_days_most_asked_first(
    ws: Ws, engine: AsyncEngine
) -> None:
    now = datetime.now(UTC)
    await make_gap(engine, workspace_id=ws.wid, topic="gift wrapping", occurrences=2)
    await make_gap(engine, workspace_id=ws.wid, topic="eggless cakes", occurrences=9)
    await make_gap(
        engine,
        workspace_id=ws.wid,
        topic="old question",
        occurrences=50,
        first_seen_at=now - timedelta(days=40),
        last_seen_at=now - timedelta(days=31),
    )
    await make_gap(engine, workspace_id=ws.wid, topic="hidden", status="dismissed", occurrences=99)

    listed = await ws.ok("GET", "/knowledge-gaps")
    assert [(g["topic"], g["occurrences"], g["examples"]) for g in listed["items"]] == [
        ("eggless cakes", 9, []),
        ("gift wrapping", 2, []),
    ]
    dismissed = await ws.ok("GET", "/knowledge-gaps?status=dismissed")
    assert [g["topic"] for g in dismissed["items"]] == ["hidden"]
    assert (await ws.call("GET", "/knowledge-gaps?status=closed")).status_code == 422

    overview = await ws.ok("GET", "/overview")
    assert overview["knowledge_gaps_open"] == 2
    with workspace_scope(uuid.UUID(ws.wid)):
        async with make_sessionmaker(engine)() as session:
            assert await open_topics(session, now=now) == ["eggless cakes", "gift wrapping"]


async def test_dismiss_hides_a_gap_until_it_is_asked_again(
    ws: Ws, engine: AsyncEngine, maker: async_sessionmaker[AsyncSession]
) -> None:
    first, again = await asked(engine, ws, "Do you deliver on Sundays?", "Sunday delivery?")
    gap_id = await record(maker, ws, "sunday delivery", first)

    dismissed = await ws.ok("POST", f"/knowledge-gaps/{gap_id}/dismiss")
    assert (dismissed["status"], dismissed["occurrences"]) == ("dismissed", 1)
    assert [e["text"] for e in dismissed["examples"]] == ["Do you deliver on Sundays?"]
    assert (await ws.ok("POST", f"/knowledge-gaps/{gap_id}/dismiss"))["status"] == "dismissed"
    assert (await ws.ok("GET", "/knowledge-gaps"))["items"] == []
    assert (await ws.ok("GET", "/overview"))["knowledge_gaps_open"] == 0

    await record(maker, ws, "sunday delivery", first)  # the same message again: still hidden
    assert (await ws.ok("GET", "/knowledge-gaps"))["items"] == []

    assert await record(maker, ws, "Sunday deliveries", again) == gap_id  # asked again
    [gap] = await gap_rows(engine)
    assert (gap["status"], gap["occurrences"], gap["dismissed_at"]) == ("open", 2, None)
    assert [g["id"] for g in (await ws.ok("GET", "/knowledge-gaps"))["items"]] == [str(gap_id)]


async def test_an_faq_answering_a_gap_removes_it(
    ws: Ws, engine: AsyncEngine, maker: async_sessionmaker[AsyncSession]
) -> None:
    dubai, later = await asked(engine, ws, "Do you ship to Dubai?", "Shipping to the UAE?")
    gap_id = await record(maker, ws, "shipping to uae", dubai)

    source = await ws.ok(
        "POST",
        "/knowledge-sources",
        201,
        json={
            "type": "faq",
            "question": "Do you ship to Dubai?",
            "body": "Yes, to all of the UAE in 7-10 days.",
            "gap_id": str(gap_id),
        },
    )

    [gap] = await gap_rows(engine)
    assert (gap["status"], str(gap["resolved_source_id"])) == ("answered", source["id"])
    assert (await ws.ok("GET", "/knowledge-gaps"))["items"] == []
    answered = await ws.ok("GET", "/knowledge-gaps?status=answered")
    assert [g["id"] for g in answered["items"]] == [str(gap_id)]
    conflict = await ws.call("POST", f"/knowledge-gaps/{gap_id}/dismiss")
    assert (conflict.status_code, conflict.json()["code"]) == (409, "conflict")

    # If the AI still can't answer later, that is a new open question, not the answered one.
    new_id = await record(maker, ws, "shipping to uae", later)
    assert new_id != gap_id
    assert [g["status"] for g in await gap_rows(engine)] == ["answered", "open"]

    missing = await ws.call(
        "POST",
        "/knowledge-sources",
        json={"type": "faq", "question": "Q?", "body": "A.", "gap_id": str(uuid.uuid4())},
    )
    assert missing.status_code == 404


async def test_an_empty_label_and_two_jobs_opening_the_same_topic(
    ws: Ws, engine: AsyncEngine, maker: async_sessionmaker[AsyncSession]
) -> None:
    m1, m2, m3 = await asked(engine, ws, "??", "Price of the red one?", "Red one price?")
    other = await record(maker, ws, " ?! ", m1)

    with workspace_scope(uuid.UUID(ws.wid)):
        async with maker() as first, maker() as second:
            opened = await record_gap(first, missing_topic="red cake price", message_id=m2, now=NOW)
            racing = asyncio.create_task(
                record_gap(second, missing_topic="Red cake price", message_id=m3, now=NOW)
            )
            await asyncio.sleep(0.3)  # the second insert waits on the open-topic unique index
            await first.commit()
            joined = await racing
            await second.commit()

    assert joined.id == opened.id
    gaps = await gap_rows(engine)
    assert sorted((g["topic"], g["id"], g["occurrences"]) for g in gaps) == [
        ("other questions", other, 1),
        ("red cake price", opened.id, 2),
    ]
