"""GR-24 follow-ups on the sandbox: a tag taken off stops a sequence, a lead stage starts one, the
sequence's numbers (per step, with the skips by reason and the replies), and the four webhook
events.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.integration.test_sequences import (
    DAY,
    desk,  # noqa: F401  (the fixture)
    enter,
    people,
    reply,
    running,
    step,
    sweep,
    tag,
)
from tests.support.broadcasts import Shop
from tests.support.sending import clean_outbox


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


async def test_taking_a_tag_off_stops_the_sequence(desk: Shop) -> None:  # noqa: F811
    asha, ben = await desk.customer("Asha Rao"), await desk.customer("Ben Cole")
    tag_id, needed = await tag(desk), await tag(desk, "Subscriber")
    sequence = await running(
        desk,
        tag_id,
        [step(DAY, template=True)],
        stop={"on_reply": True, "removed_tag_ids": [needed]},
    )
    assert sequence["stop"]["removed_tag_names"] == ["Subscriber"]
    for who in (asha, ben):
        await desk.ws.ok("POST", f"/contacts/{who.contact_id}/tags", json={"add": [needed]})
        await enter(desk, who, tag_id)

    await desk.ws.ok("POST", f"/contacts/{asha.contact_id}/tags", json={"remove": [needed]})
    by_name = {p["contact"]["display_name"]: p for p in await people(desk, sequence["id"])}
    assert (by_name["Asha Rao"]["status"], by_name["Asha Rao"]["stop_reason"]) == (
        "stopped",
        "tag_removed",
    )
    assert by_name["Asha Rao"]["stop_text"] == "A tag they needed was taken off: Subscriber"
    assert by_name["Ben Cole"]["status"] == "active"  # still has it
    # Removing a tag that is not a stop tag changes nothing.
    await desk.ws.ok("POST", f"/contacts/{ben.contact_id}/tags", json={"remove": [tag_id]})
    assert (await people(desk, sequence["id"], status="active"))[0]["contact"]["display_name"] == (
        "Ben Cole"
    )


async def test_a_lead_moving_into_a_stage_starts_the_sequence(desk: Shop) -> None:  # noqa: F811
    asha, ben = await desk.customer("Asha Rao"), await desk.customer("Ben Cole")
    created = await desk.ws.ok(
        "POST",
        "/sequences",
        201,
        json={
            "name": "Qualified follow-up",
            "social_account_id": desk.ws.account_id,
            "entry": {"type": "lead_stage", "stage": "qualified"},
            "steps": [step(60, text="Thanks for your interest, {first_name}.")],
        },
    )
    assert created["entry"]["label"] == "A lead moves into a stage: Qualified"
    await desk.ws.ok("POST", f"/sequences/{created['id']}/activate")

    await desk.ws.ok(
        "POST", f"/contacts/{asha.contact_id}/lead-stage", json={"stage": "qualified", "note": "x"}
    )
    await desk.ws.ok(
        "POST", f"/contacts/{ben.contact_id}/lead-stage", json={"stage": "won", "note": "x"}
    )
    [person] = await people(desk, created["id"])
    assert person["contact"]["display_name"] == "Asha Rao"
    assert person["entry_event"] == "Lead stage: Qualified"
    assert await sweep(desk, datetime.now(UTC) + timedelta(minutes=5)) == {"sent": 1}


async def test_a_stage_needs_a_stage_and_only_belongs_to_its_type(desk: Shop) -> None:  # noqa: F811
    base = {
        "name": "Bad",
        "social_account_id": desk.ws.account_id,
        "steps": [step(60, text="Hi")],
    }
    missing = await desk.ws.call(
        "POST", "/sequences", json={**base, "entry": {"type": "lead_stage"}}
    )
    assert missing.status_code == 422
    stray = await desk.ws.call(
        "POST", "/sequences", json={**base, "entry": {"type": "captured", "stage": "won"}}
    )
    assert stray.status_code == 422


async def test_the_numbers_per_sequence_and_per_step(desk: Shop) -> None:  # noqa: F811
    asha = await desk.customer("Asha Rao")
    never = await desk.customer("Chitra Iyer", consent=None)
    ben = await desk.customer("Ben Cole")
    tag_id = await tag(desk)
    sequence = await running(desk, tag_id, [step(DAY, template=True), step(DAY, template=True)])
    for who in (asha, never, ben):
        await enter(desk, who, tag_id)
    start = datetime.now(UTC)
    assert await sweep(desk, start + timedelta(hours=25)) == {"sent": 2, "skipped": 1}
    await reply(desk, ben)  # Ben answers the first step: stopped, and counted as a reply

    stats = await desk.ws.ok("GET", f"/sequences/{sequence['id']}/analytics")
    assert (stats["enrolled"], stats["active"], stats["stopped"]) == (3, 2, 1)
    assert stats["stopped_by"] == [{"code": "reply", "text": "They replied", "count": 1}]
    assert (stats["sent"], stats["skipped"], stats["failed"]) == (2, 1, 0)
    assert stats["skipped_by"][0]["code"] == "no_consent"
    assert stats["skipped_by"][0]["count"] == 1
    assert (stats["replied"], stats["reply_rate"]) == (1, 0.5)
    first, second = stats["steps"]
    assert (first["position"], first["reached"], first["sent"], first["replied"]) == (1, 3, 2, 1)
    assert first["share"] == 1.0
    assert (second["position"], second["reached"], second["waiting"], second["sent"]) == (
        2,
        2,
        2,
        0,
    )
    assert second["share"] == pytest.approx(0.6667, abs=0.001)
    assert stats["window_hours"] == 24

    # A second read is served from the cache, with the same numbers.
    again = await desk.ws.ok("GET", f"/sequences/{sequence['id']}/analytics")
    assert again["computed_at"] == stats["computed_at"]


async def test_analytics_of_a_sequence_nobody_entered(desk: Shop) -> None:  # noqa: F811
    tag_id = await tag(desk)
    sequence = await running(desk, tag_id)
    stats = await desk.ws.ok("GET", f"/sequences/{sequence['id']}/analytics")
    assert (stats["enrolled"], stats["sent"], stats["reply_rate"]) == (0, 0, None)
    assert [s["share"] for s in stats["steps"]] == [0.0, 0.0, 0.0]


async def test_a_stranger_cannot_read_the_numbers(desk: Shop) -> None:  # noqa: F811
    missing = await desk.ws.call("GET", "/sequences/00000000-0000-4000-8000-000000000000/analytics")
    assert missing.status_code == 404


async def test_the_four_events_reach_a_subscribed_endpoint(desk: Shop) -> None:  # noqa: F811
    asha, ben = await desk.customer("Asha Rao"), await desk.customer("Ben Cole")
    hook = await desk.ws.ok(
        "POST",
        "/webhook-endpoints",
        201,
        json={
            "url": "https://hooks.example/sequences",
            "events": [
                "sequence.enrolled",
                "sequence.step_sent",
                "sequence.completed",
                "sequence.stopped",
            ],
        },
    )
    tag_id = await tag(desk)
    await running(desk, tag_id, [step(60, text="Hello {first_name}")])
    await enter(desk, asha, tag_id)
    await enter(desk, ben, tag_id)
    assert await sweep(desk, datetime.now(UTC) + timedelta(minutes=5)) == {"sent": 2}
    # Ben is already done, so nothing stops him; a second sequence gives something to stop.
    other = await tag(desk, "Other")
    await running(desk, other, [step(DAY, template=True)])
    await enter(desk, asha, other)
    await reply(desk, asha)

    rows: list[dict[str, Any]] = await desk.rows(
        "SELECT event_type, payload FROM webhook_deliveries WHERE endpoint_id = :e"
        " ORDER BY created_at",
        e=hook["id"],
    )
    kinds = [r["event_type"] for r in rows]
    assert kinds.count("sequence.enrolled") == 3
    assert kinds.count("sequence.step_sent") == 2
    assert kinds.count("sequence.completed") == 2
    assert kinds.count("sequence.stopped") == 1
    stopped = next(r["payload"]["data"] for r in rows if r["event_type"] == "sequence.stopped")
    assert stopped["reason"] == "reply"
    assert stopped["sequence"]["name"] == "Three days"
    assert stopped["contact"]["name"] == "Asha Rao"
    sent = next(r["payload"]["data"] for r in rows if r["event_type"] == "sequence.step_sent")
    assert (sent["step"], sent["step_count"], sent["sent_as"]) == (1, 1, "text")


async def test_the_catalogue_lists_the_new_events(desk: Shop) -> None:  # noqa: F811
    listed = await desk.ws.ok("GET", "/webhook-events")
    names = {item["type"] for item in listed["items"]}
    assert {
        "sequence.enrolled",
        "sequence.step_sent",
        "sequence.completed",
        "sequence.stopped",
    } <= (names)
