"""GR-15: link click tracking and flow analytics. Done when a link click in the sandbox shows on the
step's funnel: link buttons are sent through /l/<code>, the redirect records the click (not a
preview's) against the run, step and contact, the automation can opt out, and the funnel and a
Split's results are built from the step log, the messages and the clicks."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.tenancy import workspace_scope
from socialhood.models.automations import Automation
from socialhood.services.automations import funnel
from socialhood.services.automations.runtime import Outcome
from socialhood.settings import Settings
from tests.integration.test_flow_runs import (
    LINK,
    deliver_last,
    outbound,
    ref,
    send,
    started,
    with_flow,
)
from tests.support.api import Clerk
from tests.support.automation_api import Ws, workspace
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox

BASE = "https://api.example.test"
PERSON = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) Instagram 330.0.0.34.89"
PREVIEW = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"


@pytest.fixture
def api_settings(api_settings: Settings) -> Settings:
    return api_settings.model_copy(update={"api_base_url": BASE})


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


def with_link(**first: Any) -> dict[str, Any]:
    return {
        "start": "hello",
        "steps": [send("hello", "Here it is.", buttons=[{"title": "Open", "url": LINK}], **first)],
    }


def code_of(url: str) -> str:
    assert url.startswith(f"{BASE}/l/"), url
    return url.removeprefix(f"{BASE}/l/")


async def clicks(world: World) -> list[dict[str, Any]]:
    return await world.rows("SELECT * FROM link_clicks ORDER BY created_at")


async def get_funnel(world: World, automation_id: uuid.UUID) -> Any:
    async with world.maker() as session:
        with workspace_scope(world.wid):
            automation = await session.get(Automation, automation_id)
            assert automation is not None
            return await funnel.automation_funnel(
                session, automation, days=30, now=datetime.now(UTC)
            )


# ---------------------------------------------------------------- the redirect


async def test_a_link_button_is_tracked_and_a_click_shows_on_the_steps_funnel(
    world: World, client: httpx.AsyncClient
) -> None:
    automation_id = await with_flow(world, with_link())
    author = ref()
    run = await started(world, author)
    [message] = await outbound(world)
    sent_url = message["buttons"][0]["url"]
    code = code_of(sent_url)
    # Nothing about the run, step or contact is in the address.
    for secret in (str(run["id"]), "hello", author, "link"):
        assert secret not in sent_url
    [link] = await world.rows("SELECT * FROM tracked_links")
    assert (link["code"], link["url"], link["step_id"], link["run_id"]) == (
        code,
        LINK,
        "hello",
        run["id"],
    )

    # A preview fetcher and a HEAD request get the redirect but aren't counted.
    preview = await client.get(f"/l/{code}", headers={"user-agent": PREVIEW})
    assert (preview.status_code, preview.headers["location"]) == (302, LINK)
    head = await client.head(f"/l/{code}", headers={"user-agent": PERSON})
    assert head.status_code == 302
    assert await clicks(world) == []

    # A person is redirected and counted against the run, step and contact.
    person = await client.get(f"/l/{code}", headers={"user-agent": PERSON})
    assert (person.status_code, person.headers["location"]) == (302, LINK)
    assert person.headers["cache-control"] == "no-store"
    [click] = await clicks(world)
    assert (click["run_id"], click["step_id"], click["automation_id"]) == (
        run["id"],
        "hello",
        automation_id,
    )
    assert click["contact_id"] == link["contact_id"]

    # Tapping twice at once counts once; a later click counts again.
    await client.get(f"/l/{code}", headers={"user-agent": PERSON})
    assert len(await clicks(world)) == 1
    async with world.engine.begin() as conn:
        await conn.execute(text("UPDATE link_clicks SET created_at = now() - interval '1 minute'"))
    await client.get(f"/l/{code}", headers={"user-agent": PERSON})
    assert len(await clicks(world)) == 2

    result = await get_funnel(world, automation_id)
    [step] = result.steps
    assert (step.step_id, step.reached, step.sent, step.link_clicks, step.link_clickers) == (
        "hello",
        1,
        1,
        2,
        1,
    )
    assert result.links_tracked is True


async def test_an_unknown_code_or_an_unsafe_address_is_not_followed(
    world: World, client: httpx.AsyncClient
) -> None:
    await with_flow(world, with_link())
    await started(world, ref())
    [message] = await outbound(world)
    code = code_of(message["buttons"][0]["url"])

    assert (await client.get("/l/" + "x" * 16, headers={"user-agent": PERSON})).status_code == 404
    assert (await client.get("/l/short", headers={"user-agent": PERSON})).status_code == 422
    async with world.engine.begin() as conn:
        await conn.execute(text("UPDATE tracked_links SET url = 'javascript:alert(1)'"))
    unsafe = await client.get(f"/l/{code}", headers={"user-agent": PERSON})
    assert unsafe.status_code == 404
    assert await clicks(world) == []


async def test_the_profile_button_is_never_tracked(world: World) -> None:
    await with_flow(
        world,
        {
            "start": "hello",
            "steps": [
                send("hello", "Follow us.", buttons=[{"title": "View profile", "profile": True}])
            ],
        },
    )
    await started(world, ref())
    [message] = await outbound(world)
    assert message["buttons"][0]["url"].startswith("https://www.instagram.com/")
    assert await world.rows("SELECT 1 FROM tracked_links") == []


async def test_an_automation_can_send_the_raw_link(world: World) -> None:
    automation_id = await with_flow(world, with_link())
    async with world.engine.begin() as conn:
        await conn.execute(
            text("UPDATE automations SET track_links = false WHERE id = :a"), {"a": automation_id}
        )
    await started(world, ref())
    [message] = await outbound(world)
    assert message["buttons"] == [{"title": "Open", "url": LINK}]
    assert await world.rows("SELECT 1 FROM tracked_links") == []
    result = await get_funnel(world, automation_id)
    assert result.links_tracked is False


async def test_without_a_link_domain_the_raw_link_is_sent(
    world: World, api_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(world.deps.settings, "api_base_url", None)
    await with_flow(world, with_link())
    await started(world, ref())
    [message] = await outbound(world)
    assert message["buttons"] == [{"title": "Open", "url": LINK}]


async def test_a_message_on_the_settings_is_tracked_too(
    world: World, client: httpx.AsyncClient
) -> None:
    from tests.support.automations import make_automation

    automation_id = await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        message_text="Here you go",
        message_buttons=[{"title": "Shop", "url": LINK}],
    )
    dm = await world.dm(ref(), "link please")
    assert dm is not None
    await world.run("dm", dm)
    message = await deliver_last(world)
    code = code_of(message["buttons"][0]["url"])
    await client.get(f"/l/{code}", headers={"user-agent": PERSON})
    [click] = await clicks(world)
    assert click["step_id"] == "message"
    result = await get_funnel(world, automation_id)
    [step] = [s for s in result.steps if s.step_id == "message"]
    assert (step.reached, step.sent, step.link_clicks) == (1, 1, 1)


# ---------------------------------------------------------------- the funnel


def captured_flow() -> dict[str, Any]:
    return {
        "start": "hello",
        "steps": [
            send(
                "hello",
                "Want the guide?",
                quick_replies=[{"title": "Yes", "next": "email"}, {"title": "No", "next": None}],
            ),
            {
                "type": "ask",
                "id": "email",
                "text": "Your email?",
                "expect": "email",
                "next": "guide",
            },
            send("guide", "Here it is.", buttons=[{"title": "Open", "url": LINK}]),
        ],
    }


async def test_the_funnel_counts_each_stage_of_a_step(
    world: World, client: httpx.AsyncClient
) -> None:
    automation_id = await with_flow(world, captured_flow())
    author = ref()
    run = await started(world, author)
    tap = await world.dm(author, "Yes", payload=f"shf:{run['id']}:hello:0")
    assert tap is not None
    assert await world.run("dm", tap) is Outcome.ANSWERED
    assert await world.run("flow", run["id"]) is Outcome.FIRED
    await deliver_last(world)
    email = await world.dm(author, "Priya@Example.com")
    assert email is not None
    assert await world.run("dm", email) is Outcome.ANSWERED
    assert await world.run("flow", run["id"]) is Outcome.FIRED
    guide = await deliver_last(world)
    async with world.engine.begin() as conn:
        await conn.execute(
            text("UPDATE messages SET status = 'read' WHERE id = :m"), {"m": guide["id"]}
        )
    await client.get(
        f"/l/{guide['buttons'][0]['url'].rsplit('/', 1)[1]}", headers={"user-agent": PERSON}
    )

    result = await get_funnel(world, automation_id)
    by_step = {s.step_id: s for s in result.steps}
    assert [s.step_id for s in result.steps] == ["hello", "email", "guide"]
    hello, ask, final = by_step["hello"], by_step["email"], by_step["guide"]
    assert (hello.reached, hello.sent, hello.taps) == (1, 1, 1)
    assert (ask.reached, ask.sent, ask.captures, ask.skipped) == (1, 1, 1, 0)
    assert (final.reached, final.sent, final.delivered, final.read, final.link_clicks) == (
        1,
        1,
        1,
        1,
        1,
    )
    assert result.runs == 1


def split_flow() -> dict[str, Any]:
    return {
        "start": "split",
        "steps": [
            {
                "type": "randomize",
                "id": "split",
                "paths": [{"weight": 1, "next": "a"}, {"weight": 1, "next": "b"}],
            },
            send("a", "Message A", buttons=[{"title": "Open A", "url": LINK}]),
            send("b", "Message B", buttons=[{"title": "Open B", "url": LINK}]),
        ],
    }


async def test_a_splits_results_are_counted_per_path(
    world: World, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from socialhood.services.automations import engine

    automation_id = await with_flow(world, split_flow(), cooldown_hours=0)
    picks = iter([0, 0, 1])
    monkeypatch.setattr(engine, "_pick", lambda weights: next(picks))
    for _ in range(3):
        author = ref()
        dm = await world.dm(author, "link please")
        assert dm is not None
        await world.run("dm", dm)
        message = await deliver_last(world)
        code = message["buttons"][0]["url"].rsplit("/", 1)[1]
        await client.get(f"/l/{code}", headers={"user-agent": PERSON})
    result = await get_funnel(world, automation_id)
    [split] = result.splits
    assert split.step_id == "split"
    a, b = split.branches
    assert (a.label, a.runs, a.delivered, a.link_clicks) == ("Path A", 2, 0, 2)
    assert (b.label, b.runs, b.delivered, b.link_clicks) == ("Path B", 1, 0, 1)


# ---------------------------------------------------------------- the API


async def test_the_funnel_route_is_for_admins_and_stays_in_the_workspace(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    from tests.support.api import sign_in

    ws: Ws = await workspace(client, clerk)
    draft = await ws.draft()
    flow = await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=split_flow())
    assert flow["version"] == 1

    body = await ws.ok("GET", f"/automations/{draft['id']}/funnel", params={"days": 7})
    assert (body["days"], body["runs"], body["links_tracked"]) == (7, 0, True)
    assert [s["step_id"] for s in body["steps"]] == ["split", "a", "b"]
    assert body["steps"][1]["reached"] == 0
    assert [b["label"] for b in body["splits"][0]["branches"]] == ["Path A", "Path B"]
    assert (
        await ws.call("GET", f"/automations/{draft['id']}/funnel", params={"days": 5})
    ).status_code == 422

    other = await workspace(client, clerk, email="other@example.com")
    crossed = await other.call("GET", f"/automations/{draft['id']}/funnel")
    assert crossed.status_code == 404

    clerk_id, me = await sign_in(client, clerk, email="agent@example.com")
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO workspace_members (workspace_id, user_id, role)"
                " VALUES (:w, :u, 'agent')"
            ),
            {"w": ws.wid, "u": me["id"]},
        )
    denied = await client.get(
        f"/v1/w/{ws.wid}/automations/{draft['id']}/funnel", headers=clerk.headers(clerk_id)
    )
    assert denied.status_code == 403


async def test_the_opt_out_is_saved_with_the_automation(
    client: httpx.AsyncClient, clerk: Clerk
) -> None:
    ws: Ws = await workspace(client, clerk)
    draft = await ws.draft()
    assert draft["track_links"] is True
    off = await ws.ok("PUT", f"/automations/{draft['id']}", json=ws.definition(track_links=False))
    assert off["track_links"] is False
    # Left out of a later save, it keeps what was saved.
    kept = await ws.ok("PUT", f"/automations/{draft['id']}", json=ws.definition())
    assert kept["track_links"] is False
    copy = await ws.ok("POST", f"/automations/{draft['id']}/duplicate", 201)
    assert copy["track_links"] is False
