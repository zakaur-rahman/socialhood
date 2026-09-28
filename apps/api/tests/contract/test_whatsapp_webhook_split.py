"""TR-WH-03/04 for WhatsApp: one event per message and per status, keys stable on re-delivery."""

from __future__ import annotations

import copy

from socialhood.platforms.whatsapp.webhooks import split_payload
from tests.support.instagram import fixture
from tests.support.whatsapp import PHONE_NUMBER_ID, WABA_ID


def test_a_message_becomes_one_event_routed_by_phone_number_id() -> None:
    [event] = split_payload(fixture("whatsapp_webhook_text.json"))
    assert event.event_type == "message"
    assert (
        event.dedupe_key == "wa:msg:wamid.HBgMOTE5ODEyMzQ1Njc4FQIAEhggM0E0QTY1OTlBRUUwMzgxMDE0NEYA"
    )
    assert event.account_ref == PHONE_NUMBER_ID
    assert event.payload["entry_id"] == WABA_ID
    assert event.payload["contact"] == {"profile": {"name": "Priya Shah"}, "wa_id": "919812345678"}
    assert event.payload["message"]["text"] == {"body": "Do you ship to Pune?"}


def test_each_message_of_a_batch_keeps_its_own_sender() -> None:
    events = split_payload(fixture("whatsapp_webhook_other.json"))
    assert len(events) == 8
    assert [e.event_type for e in events].count("reaction") == 2
    button = next(e for e in events if e.payload["message"]["type"] == "button")
    assert button.payload["contact"]["profile"]["name"] == "Arjun Rao"


def test_statuses_are_keyed_by_message_and_status() -> None:
    events = split_payload(fixture("whatsapp_webhook_statuses.json"))
    assert [e.event_type for e in events] == ["status"] * 4
    assert [e.dedupe_key for e in events] == [
        "wa:status:wamid.OUTBOUND000000000000000000000000000000001:sent",
        "wa:status:wamid.OUTBOUND000000000000000000000000000000001:delivered",
        "wa:status:wamid.OUTBOUND000000000000000000000000000000001:read",
        "wa:status:wamid.OUTBOUND000000000000000000000000000000002:failed",
    ]
    assert {e.account_ref for e in events} == {PHONE_NUMBER_ID}


def test_keys_are_stable_across_redelivery() -> None:
    for name in ("whatsapp_webhook_media.json", "whatsapp_webhook_statuses.json"):
        body = fixture(name)
        first = [e.dedupe_key for e in split_payload(body)]
        assert first == [e.dedupe_key for e in split_payload(copy.deepcopy(body))]
        assert len(set(first)) == len(first)


def test_other_fields_are_kept_under_the_business_account() -> None:
    [event] = split_payload(fixture("whatsapp_webhook_template_status.json"))
    assert event.event_type == "message_template_status_update"
    assert event.account_ref == WABA_ID
    assert event.dedupe_key.startswith(f"wa:message_template_status_update:{WABA_ID}:")


def test_an_error_only_change_is_kept() -> None:
    body = fixture("whatsapp_webhook_text.json")
    value = body["entry"][0]["changes"][0]["value"]
    del value["messages"], value["contacts"]
    value["errors"] = [{"code": 131000, "title": "Something went wrong"}]
    [event] = split_payload(body)
    assert event.event_type == "error"
    assert event.account_ref == PHONE_NUMBER_ID


def test_junk_is_skipped() -> None:
    assert split_payload({}) == []
    assert split_payload({"entry": ["x", None, {"changes": ["y", None]}]}) == []
    assert split_payload({"entry": "not a list"}) == []
