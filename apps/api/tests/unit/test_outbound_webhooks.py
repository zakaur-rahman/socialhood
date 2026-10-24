"""GR-04: outbound webhooks without a database. Signing (a receiver using Standard Webhooks
accepts it), the retry schedule, the envelope, what counts as a contact change, the SSRF rules on
the POST, and the endpoint address rules."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
from socialhood.models.inbox import Contact
from socialhood.security import ssrf
from socialhood.security.signatures import verify_standard_webhook
from socialhood.services.contacts import changes
from socialhood.services.webhooks import delivery, endpoints, events

NOW = datetime(2026, 10, 24, 9, 30, tzinfo=UTC)


def test_a_signed_delivery_verifies_with_the_endpoints_secret() -> None:
    secret = endpoints.new_secret()
    assert secret.startswith("whsec_")
    event_id = uuid.uuid4()
    payload = {"id": str(event_id), "type": "lead.captured", "data": {"email": "a@b.in"}}
    body, headers = delivery.sign(event_id, payload, secret, datetime.now(UTC))
    assert json.loads(body) == payload
    assert headers["webhook-id"] == str(event_id)
    assert headers["webhook-signature"].startswith("v1,")
    assert verify_standard_webhook(body, headers, secret)
    assert not verify_standard_webhook(body, headers, endpoints.new_secret())
    assert not verify_standard_webhook(body + b" ", headers, secret)


def test_retries_back_off_then_stop() -> None:
    waits = [delivery.backoff(n) for n in range(1, delivery.MAX_ATTEMPTS + 1)]
    assert waits[:-1] == [
        timedelta(minutes=1),
        timedelta(minutes=5),
        timedelta(minutes=30),
        timedelta(hours=2),
        timedelta(hours=6),
        timedelta(hours=12),
    ]
    assert waits[-1] is None  # the 7th attempt is the last


def test_the_envelope() -> None:
    wid = uuid.uuid4()
    with workspace_scope(wid):
        body = events.envelope("contact.created", {"contact": {"id": "c"}}, now=NOW)
    assert set(body) == {"id", "type", "version", "created_at", "workspace_id", "data"}
    assert (body["type"], body["version"], body["workspace_id"]) == ("contact.created", 1, str(wid))
    assert body["created_at"] == NOW.isoformat()
    uuid.UUID(body["id"])


def test_every_event_is_catalogued_with_a_version() -> None:
    names = [e.name for e in events.EVENTS]
    assert len(names) == len(set(names)) == 9
    assert {e.name for e in events.EVENTS if not e.emitted} == {"broadcast.finished"}
    listed = endpoints.catalogue()
    assert [i.type for i in listed.items] == names


def test_what_counts_as_a_contact_change() -> None:
    contact = Contact(email="new@x.in", phone="+919876543210", fields={"city": "Pune", "size": "M"})
    before = ("old@x.in", "+919876543210", {"city": "Goa", "tier": "gold"})
    assert changes(before, contact) == ["email", "fields.city", "fields.size", "fields.tier"]
    assert changes(("new@x.in", "+919876543210", {"city": "Pune", "size": "M"}), contact) == []


async def test_a_post_goes_to_a_public_address_only() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    async def public(host: str, port: int) -> list[str]:
        return ["93.184.216.34"]

    posted = await ssrf.post_json(
        "https://hooks.example.com/in",
        b"{}",
        {"webhook-id": "1"},
        resolve=public,
        transport=httpx.MockTransport(handler),
    )
    assert posted.status == 204
    [request] = seen
    assert request.method == "POST"
    assert request.url.host == "93.184.216.34"  # the checked address, the name in Host
    assert request.headers["host"] == "hooks.example.com"
    assert request.headers["content-type"] == "application/json"

    async def private(host: str, port: int) -> list[str]:
        return ["10.0.0.5"]

    with pytest.raises(ssrf.FetchError) as blocked:
        await ssrf.post_json("https://hooks.example.com/in", b"{}", {}, resolve=private)
    assert blocked.value.code == "blocked"
    with pytest.raises(ssrf.FetchError):
        await ssrf.post_json("http://127.0.0.1:9/in", b"{}", {})


async def test_a_local_receiver_is_allowed_where_configured() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "127.0.0.1"
        return httpx.Response(200)

    posted = await ssrf.post_json(
        "http://127.0.0.1:8999/hook",
        b"{}",
        {},
        allow_private=True,
        transport=httpx.MockTransport(handler),
    )
    assert posted.status == 200


def test_endpoint_addresses_are_https() -> None:
    assert endpoints._url(" https://hooks.example.com/in ", allow_private=False) == (
        "https://hooks.example.com/in"
    )
    for bad in ("http://hooks.example.com/in", "https://user:pw@hooks.example.com", "ftp://x.in"):
        with pytest.raises(ApiError) as refused:
            endpoints._url(bad, allow_private=False)
        assert refused.value.errors[0].field == "url"
    with pytest.raises(ApiError):
        endpoints._url("https://10.1.2.3/hook", allow_private=False)
    assert endpoints._url("http://127.0.0.1:8999/hook", allow_private=True) == (
        "http://127.0.0.1:8999/hook"
    )
