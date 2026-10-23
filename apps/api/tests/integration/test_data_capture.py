"""GR-14: data capture and consent. Done when a captured email lands on the contact, raises
lead.captured for a webhook endpoint, and appears in the CSV export; plus phone and text answers,
the retry and skip paths, the consent question with its evidence, and the confirmation."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.tenancy import workspace_scope
from socialhood.schemas.integrations import WebhookEndpointCreate
from socialhood.services import contacts
from socialhood.services.automations.runtime import Outcome
from socialhood.services.webhooks import endpoints
from socialhood.settings import Settings
from tests.integration.test_flow_runs import (
    deliver_last,
    outbound,
    ref,
    send,
    started,
    steps,
    with_flow,
)
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox

HOOK = "https://hooks.example.com/leads"


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


@pytest.fixture
async def world(
    engine: AsyncEngine,
    redis: Redis,
    api_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    clean_db: None,
    queue: None,
) -> AsyncIterator[World]:
    async with platform_deps(api_settings, monkeypatch) as deps:
        yield await make_world(engine, redis, deps)


def question(**kw: Any) -> dict[str, Any]:
    return {
        "start": "q",
        "steps": [
            {
                "type": "ask",
                "id": "q",
                "text": "Your email?",
                "expect": "email",
                "next": "after",
                **kw,
            },
            send("after", "Done."),
        ],
    }


async def say(world: World, author: str, text_: str, **kw: Any) -> Any:
    msg = await world.dm(author, text_, **kw)
    assert msg is not None
    assert await world.run("dm", msg) is Outcome.ANSWERED
    return msg


async def contact_of(world: World, author: str) -> dict[str, Any]:
    [row] = await world.rows("SELECT * FROM contacts WHERE platform_user_id = :r", r=author)
    return row


async def test_a_captured_email_lands_on_the_contact_the_webhook_and_the_export(
    world: World,
) -> None:
    with workspace_scope(world.wid):
        async with world.maker() as session:
            await endpoints.create(
                session,
                WebhookEndpointCreate(url=HOOK, events=["lead.captured"]),  # type: ignore[arg-type]
                cipher=world.deps.cipher,
                user_id=None,
                allow_private=False,
            )
            await session.commit()
    await with_flow(world, question())
    author = ref()
    run = await started(world, author)
    await say(world, author, " Priya@Example.com ")

    contact = await contact_of(world, author)
    assert (contact["email"], contact["email_source"]) == ("priya@example.com", "flow")
    [lead] = await world.rows(
        "SELECT payload FROM webhook_deliveries WHERE event_type = 'lead.captured'"
    )
    assert lead["payload"]["data"]["captured"] == {
        "kind": "email",
        "field_key": None,
        "value": "priya@example.com",
    }

    with workspace_scope(world.wid):
        async with world.maker() as session:
            lines = [r async for r in contacts.export_rows(session, contacts.ContactFilter())]
    header, *rows = lines
    assert [r[header.index("Email")] for r in rows] == ["priya@example.com"]
    log = await steps(world, run["id"])
    assert log["q"]["detail"] == {"tries": 1, "answer": "priya@example.com"}


async def test_a_phone_answer_is_saved_as_e164(world: World) -> None:
    await with_flow(
        world,
        {
            "start": "q",
            "steps": [{"type": "ask", "id": "q", "text": "Your number?", "expect": "phone"}],
        },
    )
    author = ref()
    await started(world, author)
    await say(world, author, "98765 43210")
    contact = await contact_of(world, author)
    assert (contact["phone"], contact["phone_source"]) == ("+919876543210", "flow")


async def test_a_long_text_answer_is_retried_then_skipped_to_the_skip_path(world: World) -> None:
    await with_flow(
        world,
        {
            "start": "q",
            "steps": [
                {
                    "type": "ask",
                    "id": "q",
                    "text": "Your city?",
                    "expect": "text",
                    "field_key": "city",
                    "tries": 2,
                    "retry_text": "Too long. Just the city name.",
                    "on_skip": "skipped",
                    "next": "after",
                },
                send("after", "Thanks."),
                send("skipped", "No problem, carry on."),
            ],
        },
    )
    async with world.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO contact_field_definitions (workspace_id, key, label, type, position)"
                " VALUES (:w, 'city', 'City', 'text', 0)"
            ),
            {"w": world.wid},
        )
    author = ref()
    run = await started(world, author)
    await say(world, author, "x" * 501)
    assert (await outbound(world))[-1]["text"] == "Too long. Just the city name."
    await say(world, author, "y" * 501)
    run = await world.run_row(run["id"])
    assert (run["flow_state"], run["step_id"]) == ("next", "skipped")
    log = await steps(world, run["id"])
    assert log["q"]["detail"]["skipped"] is True
    assert not (await contact_of(world, author))["fields"]


async def test_a_consent_question_follows_the_answer_and_records_its_evidence(
    world: World,
) -> None:
    await with_flow(
        world,
        question(consent=True, consent_text="Can we send offers here?", confirm_text="Thanks."),
    )
    author = ref()
    run = await started(world, author)
    await say(world, author, "priya@example.com")
    ask_consent = await deliver_last(world)
    assert ask_consent["text"] == "Can we send offers here?"
    assert [q["title"] for q in ask_consent["quick_replies"]] == ["Yes", "No thanks"]
    assert (await world.run_row(run["id"]))["flow_state"] == "replying"

    # Neither a yes nor a no: asked once more.
    await say(world, author, "hmm")
    again = await deliver_last(world)
    assert again["text"].startswith("Sorry, I need a yes or a no")
    answer = await say(world, author, "Yes", payload=ask_consent["quick_replies"][0]["payload"])

    contact = await contact_of(world, author)
    [consent] = await world.rows(
        "SELECT * FROM contact_consents WHERE contact_id = :c", c=contact["id"]
    )
    assert (consent["channel"], consent["status"], consent["source"], consent["purpose"]) == (
        "instagram",
        "granted",
        "flow",
        "marketing",
    )
    evidence = consent["evidence"]
    assert evidence["message_id"] == str(answer)
    assert evidence["text"] == "Yes"
    assert evidence["channel"] == "instagram"
    assert evidence["question_message_id"] == str(again["id"])  # the latest time it was asked
    assert evidence["run_id"] == str(run["id"])
    assert consent["occurred_at"] is not None
    assert (await outbound(world))[-1]["text"] == "Thanks."
    assert (await world.run_row(run["id"]))["flow_state"] == "next"
    assert (await steps(world, run["id"]))["q"]["detail"]["consent"] == "granted"


async def test_declining_is_recorded(world: World) -> None:
    await with_flow(world, question(consent=True))
    author = ref()
    await started(world, author)
    await say(world, author, "priya@example.com")
    await deliver_last(world)
    await say(world, author, "no thanks")
    contact = await contact_of(world, author)
    [consent] = await world.rows(
        "SELECT status FROM contact_consents WHERE contact_id = :c", c=contact["id"]
    )
    assert consent["status"] == "revoked"


async def test_two_unclear_answers_record_nothing_and_the_flow_goes_on(world: World) -> None:
    await with_flow(world, question(consent=True))
    author = ref()
    run = await started(world, author)
    await say(world, author, "o@example.com")
    await deliver_last(world)
    await say(world, author, "what?")
    await deliver_last(world)
    await say(world, author, "still unsure")
    assert await world.rows("SELECT 1 FROM contact_consents") == []
    assert (await world.run_row(run["id"]))["flow_state"] == "next"
    assert (await steps(world, run["id"]))["q"]["detail"]["consent"] == "none"


async def test_a_question_without_consent_asks_no_consent_question(world: World) -> None:
    await with_flow(world, question())
    author = ref()
    await started(world, author)
    await say(world, author, "priya@example.com")
    assert len(await outbound(world)) == 1
    assert await world.rows("SELECT 1 FROM contact_consents") == []
