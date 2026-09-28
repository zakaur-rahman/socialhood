"""T3.6/T3.7 rules that need no database: text limits (TR-PL-10), message parts (F-07), delivery
URLs and folders (TR-MED-01, TR-MED-02), idempotency fingerprints (TR-API-05)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from socialhood.errors import ApiError
from socialhood.models.inbox import Message
from socialhood.platforms.buckets import Bucket
from socialhood.services import media_assets, sending
from socialhood.services.idempotency import fingerprint


def test_instagram_counts_bytes_and_whatsapp_characters() -> None:
    assert sending.text_limit_error("instagram", "a" * 1000) is None
    assert sending.text_limit_error("instagram", "😀" * 250) is None  # 4 bytes each
    assert sending.text_limit_error("instagram", "😀" * 251) == (
        "Instagram messages can be up to 1,000 bytes; this one is 1,004."
    )
    assert sending.text_limit_error("whatsapp", "😀" * 4096) is None
    assert sending.text_limit_error("whatsapp", "a" * 4097) == (
        "WhatsApp messages can be up to 4,096 characters; this one is 4,097."
    )


def test_readable_reasons_follow_the_copy() -> None:
    assert sending.readable_error("platform_rejected", "instagram", platform_message="Bad") == (
        "Instagram rejected this: Bad"
    )
    assert sending.readable_error("account_needs_reconnect", "instagram", username="maple") == (
        "@maple needs reconnecting before you can send from it."
    )
    assert "Send an approved template instead." in sending.readable_error(
        "reply_window_closed", "whatsapp"
    )


def message(**values: object) -> Message:
    base: dict[str, object] = {
        "id": uuid.uuid4(),
        "conversation_id": uuid.uuid4(),
        "direction": "outbound",
        "source": "human",
        "kind": "text",
        "text": "See both",
        "attachments": [],
        "occurred_at": datetime.now(UTC),
        "status": "queued",
        "human_agent_tag": False,
        "reactions": [],
    }
    return Message(**{**base, **values})


def test_attachments_go_first_one_per_part_and_sent_parts_are_skipped() -> None:
    attachments = [
        {"type": "image", "url": "u1", "send_url": "s1", "sent": True, "platform_message_id": "m"},
        {"type": "image", "url": "u2", "send_url": "s2"},
    ]
    parts = sending.pending_parts(message(attachments=attachments), "instagram", human_agent=True)
    assert [p.attachment_index for p in parts] == [1, None]
    assert parts[0].message.attachment is not None
    assert parts[0].message.attachment.url == "s2"
    assert parts[0].bucket == Bucket.IG_SEND_MEDIA
    assert parts[1].message.text == "See both"
    assert parts[1].bucket == Bucket.IG_SEND
    assert all(p.message.human_agent for p in parts)


def test_a_template_is_its_own_part() -> None:
    template = {"name": "order_update", "language": "en", "params": ["Asha"]}
    [part] = sending.pending_parts(
        message(text=None, template=template), "whatsapp", human_agent=False
    )
    assert part.message.template is not None
    assert part.message.template.params == ("Asha",)
    assert part.bucket == Bucket.WA_SEND


def test_images_and_videos_are_delivered_in_platform_formats() -> None:
    url = "https://res.cloudinary.com/demo/image/upload/v17/ws/w/message/abc.heic"
    assert media_assets.delivery_url(url, "image") == (
        "https://res.cloudinary.com/demo/image/upload/f_jpg,q_auto,w_1440,c_limit/"
        "v17/ws/w/message/abc.jpg"
    )
    video = "https://res.cloudinary.com/demo/video/upload/v1/ws/w/message/clip.mov"
    assert media_assets.delivery_url(video, "video").endswith(
        "/video/upload/vc_h264,ac_aac,f_mp4/v1/ws/w/message/clip.mp4"
    )
    pdf = "https://res.cloudinary.com/demo/raw/upload/v1/ws/w/message/price.pdf"
    assert media_assets.delivery_url(pdf, "file") == pdf


def test_only_this_workspaces_client_folders_are_accepted() -> None:
    wid = uuid.uuid4()
    assert media_assets.purpose_of(f"ws/{wid}/message/abc123", wid) == "message"
    assert media_assets.purpose_of(f"ws/{wid}/knowledge/abc123.pdf", wid) == "knowledge"
    for bad in (
        f"ws/{uuid.uuid4()}/message/abc",
        f"ws/{wid}/inbound/abc",
        f"ws/{wid}/message/a/b",
        f"ws/{wid}/message/abc?x=1",
        f"ws/{wid}/message/",
    ):
        with pytest.raises(ApiError) as raised:
            media_assets.purpose_of(bad, wid)
        assert raised.value.code == "validation_error"


def test_fingerprints_ignore_key_order_but_not_values() -> None:
    a = fingerprint("post", "/v1/x", {"text": "hi", "client_id": "1"})
    assert a == fingerprint("POST", "/v1/x", {"client_id": "1", "text": "hi"})
    assert a != fingerprint("POST", "/v1/x", {"client_id": "1", "text": "hi!"})
    assert a != fingerprint("POST", "/v1/y", {"client_id": "1", "text": "hi"})
