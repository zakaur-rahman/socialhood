"""Split a Facebook Page webhook body into events with stable dedupe keys (GR-29; TR-WH-03,
TR-WH-04).

Meta batches updates and retries for 36 hours, so every event gets a key that is identical on
re-delivery. Messenger events arrive in ``entry.messaging`` (the Page is ``entry.id``); post
activity, comments included, arrives in ``entry.changes`` with ``field: "feed"``. A delivery
receipt names several messages: it is split into one event per message, so each is stored once.
Handover ``standby`` events are not used.

Shapes follow Meta's Messenger Platform webhook reference and are unverified until a real Page
confirms them (docs/verification.md).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from socialhood.platforms.events import RawEvent


def _digest(item: Any) -> str:
    return hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()[:24]


def _messaging_events(entry_id: str, base: dict[str, Any], item: dict[str, Any]) -> list[RawEvent]:
    sender = (item.get("sender") or {}).get("id", "")
    recipient = (item.get("recipient") or {}).get("id", "")
    timestamp = item.get("timestamp", "")

    def one(kind: str, key: str, payload: dict[str, Any] | None = None) -> list[RawEvent]:
        return [
            RawEvent(key, kind, entry_id, {**base, "kind": "messaging", "item": payload or item})
        ]

    if "message" in item:
        message = item["message"] or {}
        if message.get("is_deleted"):
            return one("unsend", f"fb:unsend:{message.get('mid') or _digest(item)}")
        kind = "echo" if message.get("is_echo") else "message"
        return one(kind, f"fb:msg:{message.get('mid') or _digest(item)}")
    if "delivery" in item:
        delivery = item["delivery"] or {}
        mids = [m for m in delivery.get("mids") or [] if isinstance(m, str) and m]
        # A receipt without ids still moves the watermark, but we match messages by id only.
        events: list[RawEvent] = []
        for mid in mids:
            single = {**item, "delivery": {**delivery, "mids": [mid]}}
            events.append(
                RawEvent(
                    f"fb:delivery:{mid}",
                    "delivery",
                    entry_id,
                    {**base, "kind": "messaging", "item": single},
                )
            )
        return events
    if "read" in item:
        read = item["read"] or {}
        return one("seen", f"fb:seen:{recipient}:{sender}:{read.get('watermark') or timestamp}")
    if "reaction" in item:
        reaction = item["reaction"] or {}
        return one(
            "reaction",
            f"fb:react:{reaction.get('mid')}:{sender}:{reaction.get('action')}:{timestamp}",
        )
    if "message_edit" in item:
        edit = item["message_edit"] or {}
        return one("edit", f"fb:edit:{edit.get('mid')}:{edit.get('num_edit', 0)}")
    for other in ("postback", "referral", "optin"):
        if other in item:
            return one(other, f"fb:{other}:{sender}:{timestamp}:{_digest(item)}")
    return one("unknown", f"fb:other:{entry_id}:{_digest(item)}")


def _change_event(field: str, value: dict[str, Any]) -> tuple[str, str]:
    if field == "feed":
        item = value.get("item")
        verb = value.get("verb", "add")
        if item == "comment":
            comment_id = value.get("comment_id") or value.get("id") or _digest(value)
            return "comment", f"fb:comment:{comment_id}:{verb}"
        return "feed", f"fb:feed:{item}:{verb}:{value.get('post_id') or _digest(value)}"
    return field or "change", f"fb:{field}:{_digest(value)}"


def split_payload(body: dict[str, Any]) -> list[RawEvent]:
    events: list[RawEvent] = []
    for entry in body.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id", ""))
        base = {
            "object": body.get("object", "page"),
            "entry_id": entry_id,
            "time": entry.get("time"),
        }
        for item in entry.get("messaging") or []:
            if isinstance(item, dict):
                events += _messaging_events(entry_id, base, item)
        for change in entry.get("changes") or []:
            if not isinstance(change, dict):
                continue
            field = str(change.get("field", ""))
            value = change.get("value") or {}
            if not isinstance(value, dict):
                continue
            kind, key = _change_event(field, value)
            events.append(
                RawEvent(
                    key, kind, entry_id, {**base, "kind": "change", "field": field, "item": value}
                )
            )
    return events
