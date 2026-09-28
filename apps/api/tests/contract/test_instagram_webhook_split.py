"""TR-WH-03/04: a delivery splits into events whose dedupe keys survive re-delivery."""

from __future__ import annotations

import copy

from socialhood.platforms.instagram.webhooks import split_payload
from tests.support.instagram import fixture


def test_a_messaging_batch_splits_into_one_event_per_item() -> None:
    events = split_payload(fixture("webhook_messaging_batch.json"))
    assert [e.event_type for e in events] == ["message", "seen", "reaction"]
    assert {e.account_ref for e in events} == {"17841400000000001"}
    assert events[0].dedupe_key == "ig:msg:aWdfZAG1faXRlbToxOklHTWVzc2FnZAUlEOjE3ODQx"
    assert events[0].payload["item"]["message"]["text"] == "Do you ship to Pune?"


def test_keys_are_stable_across_redelivery() -> None:
    body = fixture("webhook_messaging_batch.json")
    first = [e.dedupe_key for e in split_payload(body)]
    again = [e.dedupe_key for e in split_payload(copy.deepcopy(body))]
    assert first == again
    assert len(set(first)) == 3


def test_an_echo_is_its_own_type() -> None:
    body = fixture("webhook_messaging_batch.json")
    body["entry"][0]["messaging"] = [body["entry"][0]["messaging"][0]]
    body["entry"][0]["messaging"][0]["message"]["is_echo"] = True
    assert split_payload(body)[0].event_type == "echo"


def test_comments_arrive_in_either_shape() -> None:
    changes = split_payload(fixture("webhook_comment_changes.json"))
    field_value = split_payload(fixture("webhook_comment_field_value.json"))
    assert [e.event_type for e in changes + field_value] == ["comment", "comment"]
    assert changes[0].dedupe_key == "ig:comment:18000000000000001:comments:add"
    assert field_value[0].payload["item"]["text"] == "Love this"


def test_unknown_items_are_kept_not_dropped() -> None:
    body = {"object": "instagram", "entry": [{"id": "1", "messaging": [{"something": "new"}]}]}
    events = split_payload(body)
    assert [e.event_type for e in events] == ["unknown"]


def test_junk_entries_are_skipped() -> None:
    assert split_payload({"object": "instagram", "entry": ["x", None]}) == []
    assert split_payload({}) == []
