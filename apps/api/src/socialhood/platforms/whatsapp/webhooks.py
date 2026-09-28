"""Split a WhatsApp webhook body into events with stable dedupe keys (TR-WH-03, TR-WH-04,
TR-PL-12).

A delivery is ``entry[]`` (one per WhatsApp Business Account) of ``changes[]``; a ``messages``
change carries ``value.messages[]`` and/or ``value.statuses[]`` for the number in
``value.metadata.phone_number_id``, which is the account we route by. Each message and each status
is its own event: ``wa:msg:{id}`` and ``wa:status:{id}:{status}``. Each stored message keeps its
sender's ``contacts[]`` entry (the profile name). Other fields (template status, account
updates, ...) are kept, not dropped, and ignored when processed.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from socialhood.platforms.events import RawEvent


def _digest(item: Any) -> str:
    return hashlib.sha256(json.dumps(item, sort_keys=True, default=str).encode()).hexdigest()[:24]


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _contact_for(contacts: list[Any], sender: Any) -> dict[str, Any] | None:
    dicts = [c for c in contacts if isinstance(c, dict)]
    for contact in dicts:
        if contact.get("wa_id") == sender:
            return contact
    return dicts[0] if len(dicts) == 1 else None


def _message_events(base: dict[str, Any], value: dict[str, Any], ref: str) -> list[RawEvent]:
    events: list[RawEvent] = []
    contacts = _list(value.get("contacts"))
    for message in _list(value.get("messages")):
        if not isinstance(message, dict):
            continue
        kind = "reaction" if message.get("type") == "reaction" else "message"
        key = f"wa:msg:{message.get('id') or _digest(message)}"
        payload = {
            **base,
            "kind": "message",
            "contact": _contact_for(contacts, message.get("from")),
            "message": message,
        }
        events.append(RawEvent(key, kind, ref, payload))
    for status in _list(value.get("statuses")):
        if not isinstance(status, dict):
            continue
        key = f"wa:status:{status.get('id') or _digest(status)}:{status.get('status', '')}"
        events.append(RawEvent(key, "status", ref, {**base, "kind": "status", "status": status}))
    if not events and value.get("errors"):
        key = f"wa:error:{ref}:{_digest(value)}"
        events.append(RawEvent(key, "error", ref, {**base, "kind": "error", "item": value}))
    return events


def split_payload(body: dict[str, Any]) -> list[RawEvent]:
    events: list[RawEvent] = []
    for entry in _list(body.get("entry")):
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id", ""))
        for change in _list(entry.get("changes")):
            if not isinstance(change, dict):
                continue
            field = str(change.get("field", ""))
            value = _dict(change.get("value"))
            metadata = _dict(value.get("metadata"))
            ref = str(metadata.get("phone_number_id") or entry_id)
            base = {
                "object": body.get("object", "whatsapp_business_account"),
                "entry_id": entry_id,
                "field": field,
                "metadata": metadata,
            }
            found = _message_events(base, value, ref) if field == "messages" else []
            if not found:
                key = f"wa:{field or 'change'}:{entry_id}:{_digest(value)}"
                found = [
                    RawEvent(key, field or "change", ref, {**base, "kind": "other", "item": value})
                ]
            events.extend(found)
    return events
