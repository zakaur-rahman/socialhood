"""Split an Instagram webhook body into events with stable dedupe keys (TR-WH-03, TR-WH-04,
TR-PL-12).

Meta batches up to 1,000 updates per request and retries for 36 hours, so every event gets a key
that is identical on re-delivery. Comment payloads come as ``changes[]`` or, for Instagram Login,
as ``field``/``value`` on the entry; both are accepted until T0.9 settles the shape.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from socialhood.platforms.events import RawEvent


def _digest(item: Any) -> str:
    return hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()[:24]


def _messaging_event(entry_id: str, item: dict[str, Any]) -> tuple[str, str]:
    sender = (item.get("sender") or {}).get("id", "")
    recipient = (item.get("recipient") or {}).get("id", "")
    timestamp = item.get("timestamp", "")
    if "message" in item:
        message = item["message"] or {}
        kind = "echo" if message.get("is_echo") else "message"
        return kind, f"ig:msg:{message.get('mid') or _digest(item)}"
    if "read" in item:
        read = item["read"] or {}
        return "seen", f"ig:seen:{recipient}:{sender}:{read.get('mid') or timestamp}"
    if "reaction" in item:
        reaction = item["reaction"] or {}
        return (
            "reaction",
            f"ig:react:{reaction.get('mid')}:{sender}:{reaction.get('action')}:{timestamp}",
        )
    if "message_edit" in item:
        edit = item["message_edit"] or {}
        return "edit", f"ig:edit:{edit.get('mid')}:{edit.get('num_edit', 0)}"
    for other in ("postback", "referral", "optin"):
        if other in item:
            return other, f"ig:{other}:{sender}:{timestamp}:{_digest(item)}"
    return "unknown", f"ig:other:{entry_id}:{_digest(item)}"


def _change_event(field: str, value: dict[str, Any]) -> tuple[str, str]:
    if field == "comments":
        return (
            "comment",
            f"ig:comment:{value.get('id') or _digest(value)}:{field}:{value.get('verb', 'add')}",
        )
    return field or "change", f"ig:{field}:{value.get('id') or _digest(value)}"


def split_payload(body: dict[str, Any]) -> list[RawEvent]:
    events: list[RawEvent] = []
    for entry in body.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id", ""))
        base = {
            "object": body.get("object", "instagram"),
            "entry_id": entry_id,
            "time": entry.get("time"),
        }
        for item in entry.get("messaging") or []:
            kind, key = _messaging_event(entry_id, item)
            events.append(
                RawEvent(key, kind, entry_id, {**base, "kind": "messaging", "item": item})
            )
        changes = list(entry.get("changes") or [])
        if "field" in entry and "value" in entry:
            changes.append({"field": entry["field"], "value": entry["value"]})
        for change in changes:
            field = str(change.get("field", ""))
            value = change.get("value") or {}
            kind, key = _change_event(field, value)
            events.append(
                RawEvent(
                    key, kind, entry_id, {**base, "kind": "change", "field": field, "item": value}
                )
            )
    return events
