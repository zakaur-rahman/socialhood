"""GR-29: the Facebook Page platform without a database - splitting a Page webhook, parsing each
field into typed events, the Send API payloads, the connect URLs and the rules a Page shares with
Instagram (reply window, text limits, entry links). Meta's shapes are unverified until a real
Page confirms them (docs/verification.md)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from socialhood.api.v1.accounts import _sandbox_facebook_payload
from socialhood.errors import ApiError
from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import (
    IceBreaker,
    OutboundAttachment,
    OutboundButton,
    OutboundMessage,
    OutboundQuickReply,
)
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError, map_graph_error
from socialhood.platforms.events import (
    DeliveryStatus,
    InboundComment,
    InboundMessage,
    MessageEdit,
    Reaction,
    ReadReceipt,
    Referral,
    Unsupported,
)
from socialhood.platforms.facebook import oauth
from socialhood.platforms.facebook.adapter import FacebookAdapter, text_content
from socialhood.platforms.facebook.comments import comment_page
from socialhood.platforms.facebook.parse import parse
from socialhood.platforms.facebook.reads import media_item
from socialhood.platforms.facebook.webhooks import split_payload
from socialhood.platforms.registry import adapter_for
from socialhood.platforms.sandbox.adapter import SandboxAdapter
from socialhood.schemas.accounts import SandboxInbound
from socialhood.security.crypto import cipher_for, new_key
from socialhood.services import sending
from socialhood.services.entry_links import link_url
from socialhood.services.reply_window import may_send, reply_window
from socialhood.settings import AppEnv, Settings

PAGE = "109876543210001"
PERSON = "7001234567890123"
NOW_MS = 1_790_000_000_000
KEY = new_key()
_ID = uuid.UUID("00000000-0000-0000-0000-00000000fb01")


def settings(**values: Any) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnv.TEST,
        database_url="postgresql+asyncpg://x:x@127.0.0.1/x",
        database_url_direct="postgresql://x:x@127.0.0.1/x",
        redis_url="redis://127.0.0.1:6379/14",
        token_encryption_keys=[KEY],
        meta_app_id="9876543210",
        meta_app_secret="fake-meta-app-secret",
        fb_redirect_uri="http://api.test/v1/oauth/facebook/callback",
        **values,
    )


def account() -> SocialAccount:
    cipher = cipher_for((KEY,))
    return SocialAccount(
        platform="facebook",
        platform_account_id=PAGE,
        username="mapleshop",
        access_token_enc=cipher.encrypt("page-token"),
        scopes=list(oauth.SCOPES),
    )


class Recorder:
    """An HTTP client whose answers a test sets, and which keeps what it was asked."""

    def __init__(self, *answers: dict[str, Any]) -> None:
        self.requests: list[httpx.Request] = []
        self.answers = list(answers) or [{"success": True}]

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        return httpx.Response(200, json=answer)

    def body(self, index: int = -1) -> dict[str, Any]:
        content = self.requests[index].content
        return json.loads(content) if content else {}

    def query(self, index: int = -1) -> dict[str, str]:
        return {k: v[0] for k, v in parse_qs(self.requests[index].url.query.decode()).items()}


def adapter(recorder: Recorder, **values: Any) -> FacebookAdapter:
    client = httpx.AsyncClient(transport=httpx.MockTransport(recorder.handler))
    config = settings(**values)
    deps = PlatformDeps(http=client, cipher=cipher_for((KEY,)), settings=config)
    return FacebookAdapter(deps)


# ---------------------------------------------------------------- webhook splitting


def messaging(entry: dict[str, Any]) -> dict[str, Any]:
    return {"object": "page", "entry": [{"id": PAGE, "time": NOW_MS, **entry}]}


def test_a_batch_splits_into_one_event_per_update_with_stable_keys() -> None:
    body = messaging(
        {
            "messaging": [
                {
                    "sender": {"id": PERSON},
                    "recipient": {"id": PAGE},
                    "timestamp": NOW_MS,
                    "message": {"mid": "m_1", "text": "hi"},
                },
                {
                    "sender": {"id": PAGE},
                    "recipient": {"id": PERSON},
                    "timestamp": NOW_MS,
                    "message": {"mid": "m_2", "text": "hello", "is_echo": True},
                },
                {
                    "sender": {"id": PERSON},
                    "recipient": {"id": PAGE},
                    "timestamp": NOW_MS,
                    "delivery": {"mids": ["m_2", "m_3"], "watermark": NOW_MS},
                },
                {
                    "sender": {"id": PERSON},
                    "recipient": {"id": PAGE},
                    "timestamp": NOW_MS,
                    "read": {"watermark": NOW_MS},
                },
                {
                    "sender": {"id": PERSON},
                    "recipient": {"id": PAGE},
                    "timestamp": NOW_MS,
                    "postback": {"title": "Get started", "payload": "GO"},
                },
            ],
            "changes": [
                {
                    "field": "feed",
                    "value": {
                        "item": "comment",
                        "verb": "add",
                        "comment_id": "c_1",
                        "post_id": f"{PAGE}_9",
                        "from": {"id": PERSON, "name": "Asha"},
                        "message": "price?",
                    },
                },
                {"field": "feed", "value": {"item": "status", "verb": "add", "post_id": "p"}},
            ],
        }
    )
    events = split_payload(body)
    assert [e.event_type for e in events] == [
        "message",
        "echo",
        "delivery",
        "delivery",
        "seen",
        "postback",
        "comment",
        "feed",
    ]
    assert {e.account_ref for e in events} == {PAGE}
    assert events[0].dedupe_key == "fb:msg:m_1"
    assert [e.dedupe_key for e in events[2:4]] == ["fb:delivery:m_2", "fb:delivery:m_3"]
    assert events[6].dedupe_key == "fb:comment:c_1:add"
    # A re-delivery produces the same keys, so the store inserts nothing new.
    assert [e.dedupe_key for e in split_payload(body)] == [e.dedupe_key for e in events]


def test_junk_entries_are_skipped_not_raised() -> None:
    assert split_payload({"entry": ["x", {"id": PAGE, "messaging": ["y"], "changes": [3]}]}) == []


# ---------------------------------------------------------------- parsing


def stored(item: dict[str, Any], *, kind: str = "messaging", field: str | None = None) -> dict:
    payload: dict[str, Any] = {"object": "page", "entry_id": PAGE, "time": NOW_MS, "kind": kind}
    if field:
        payload["field"] = field
    return {**payload, "item": item}


def person_item(**values: Any) -> dict[str, Any]:
    return {"sender": {"id": PERSON}, "recipient": {"id": PAGE}, "timestamp": NOW_MS, **values}


def test_a_text_message_has_its_contact_and_quick_reply() -> None:
    event = parse(
        stored(
            person_item(
                message={
                    "mid": "m_1",
                    "text": "Yes",
                    "quick_reply": {"payload": "shr:1"},
                    "reply_to": {"mid": "m_0"},
                }
            )
        )
    )
    assert isinstance(event, InboundMessage)
    assert (event.contact_ref, event.account_ref, event.text) == (PERSON, PAGE, "Yes")
    assert (event.quick_reply_payload, event.reply_to_id, event.is_echo) == ("shr:1", "m_0", False)
    assert event.occurred_at == datetime.fromtimestamp(NOW_MS / 1000, UTC)


def test_the_pages_own_echo_belongs_to_the_person_it_went_to() -> None:
    echo = {
        "sender": {"id": PAGE},
        "recipient": {"id": PERSON},
        "timestamp": NOW_MS,
        "message": {"mid": "m_5", "text": "Thanks!", "is_echo": True},
    }
    event = parse(stored(echo))
    assert isinstance(event, InboundMessage)
    assert (event.is_echo, event.contact_ref) == (True, PERSON)


def test_attachments_and_stickers_keep_their_kind() -> None:
    image = parse(
        stored(
            person_item(
                message={
                    "mid": "m_6",
                    "attachments": [{"type": "image", "payload": {"url": "https://cdn/x.jpg"}}],
                }
            )
        )
    )
    assert isinstance(image, InboundMessage)
    assert (image.kind, image.attachments[0].url) == ("image", "https://cdn/x.jpg")
    sticker = parse(
        stored(
            person_item(
                message={
                    "mid": "m_7",
                    "attachments": [
                        {"type": "image", "payload": {"url": "https://cdn/s.png", "sticker_id": 1}}
                    ],
                }
            )
        )
    )
    assert isinstance(sticker, InboundMessage)
    assert sticker.kind == "sticker"
    location = parse(
        stored(person_item(message={"mid": "m_8", "attachments": [{"type": "location"}]}))
    )
    assert isinstance(location, InboundMessage)
    assert location.kind == "unsupported"


def test_a_postback_without_an_id_still_becomes_the_persons_message() -> None:
    event = parse(stored(person_item(postback={"title": "Get started", "payload": "GET_STARTED"})))
    assert isinstance(event, InboundMessage)
    assert (event.text, event.postback_payload) == ("Get started", "GET_STARTED")
    assert event.platform_message_id.startswith("postback_")


def test_a_link_and_an_ad_referral() -> None:
    link = parse(
        stored(
            person_item(referral={"ref": "spring", "source": "SHORTLINK", "type": "OPEN_THREAD"})
        )
    )
    assert isinstance(link, Referral)
    assert (link.referral.source, link.referral.ref) == ("link", "spring")
    ad = parse(
        stored(
            person_item(
                message={
                    "mid": "m_9",
                    "text": "price?",
                    "referral": {
                        "source": "ADS",
                        "type": "OPEN_THREAD",
                        "ad_id": "ad_1",
                        "ads_context_data": {"ad_title": "Autumn sale"},
                    },
                }
            )
        )
    )
    assert isinstance(ad, InboundMessage)
    assert ad.referral is not None
    assert (ad.referral.source, ad.referral.ad_id, ad.referral.ad_title) == (
        "ad",
        "ad_1",
        "Autumn sale",
    )


def test_a_read_is_a_watermark_and_a_delivery_names_its_message() -> None:
    read = parse(stored(person_item(read={"watermark": NOW_MS + 5000})))
    assert isinstance(read, ReadReceipt)
    assert read.last_read_message_id is None
    assert read.occurred_at == datetime.fromtimestamp((NOW_MS + 5000) / 1000, UTC)
    delivered = parse(stored(person_item(delivery={"mids": ["m_2"], "watermark": NOW_MS})))
    assert isinstance(delivered, DeliveryStatus)
    assert (delivered.platform_message_id, delivered.status) == ("m_2", "delivered")
    own_read = parse(
        stored({"sender": {"id": PAGE}, "recipient": {"id": PERSON}, "read": {"watermark": 1}})
    )
    assert isinstance(own_read, Unsupported)
    assert isinstance(parse(stored(person_item(delivery={"watermark": 1}))), Unsupported)


def test_reactions_and_edits_use_the_shared_shapes() -> None:
    reaction = parse(stored(person_item(reaction={"mid": "m_1", "action": "react", "emoji": "❤"})))
    assert isinstance(reaction, Reaction)
    assert reaction.emoji == "❤"
    edit = parse(stored(person_item(message_edit={"mid": "m_1", "text": "new", "num_edit": 1})))
    assert isinstance(edit, MessageEdit)


def comment(**values: Any) -> dict[str, Any]:
    return {
        "item": "comment",
        "verb": "add",
        "comment_id": f"{PAGE}_9_5",
        "post_id": f"{PAGE}_9",
        "parent_id": f"{PAGE}_9",
        "from": {"id": PERSON, "name": "Asha Rao"},
        "message": "How much?",
        "created_time": NOW_MS // 1000,
        **values,
    }


def test_a_new_comment_on_a_post_is_a_top_level_comment() -> None:
    event = parse(stored(comment(), kind="change", field="feed"))
    assert isinstance(event, InboundComment)
    assert (event.media_id, event.parent_id, event.author_ref) == (f"{PAGE}_9", None, PERSON)
    assert (event.author_username, event.text) == ("Asha Rao", "How much?")
    assert event.occurred_at == datetime.fromtimestamp(NOW_MS // 1000, UTC)


def test_a_reply_keeps_its_parent_comment() -> None:
    event = parse(stored(comment(parent_id=f"{PAGE}_9_4"), kind="change", field="feed"))
    assert isinstance(event, InboundComment)
    assert event.parent_id == f"{PAGE}_9_4"


@pytest.mark.parametrize(
    "value",
    [
        comment(verb="edited"),
        comment(verb="remove"),
        comment(item="status"),
        comment(item="reaction"),
        comment(**{"from": {}}),
        comment(comment_id=None, id=None),
    ],
    ids=["edited", "removed", "status", "reaction", "no-author", "no-id"],
)
def test_only_new_readable_comments_become_comments(value: dict[str, Any]) -> None:
    assert isinstance(parse(stored(value, kind="change", field="feed")), Unsupported)


def test_other_fields_and_unreadable_events_are_unsupported() -> None:
    assert isinstance(parse(stored({"anything": 1}, kind="change", field="ratings")), Unsupported)
    assert isinstance(parse({"entry_id": PAGE, "kind": "messaging", "item": "x"}), Unsupported)


# ---------------------------------------------------------------- reads


def test_posts_map_to_media_items() -> None:
    photo = media_item(
        {
            "id": f"{PAGE}_1",
            "message": "New colours",
            "created_time": "2026-10-20T10:00:00+0000",
            "full_picture": "https://cdn/p.jpg",
            "permalink_url": "https://www.facebook.com/p/1",
            "attachments": {"data": [{"type": "photo"}]},
            "comments": {"summary": {"total_count": 4}},
            "reactions": {"summary": {"total_count": 12}},
        }
    )
    assert photo is not None
    assert (photo.media_type, photo.comments_count, photo.like_count) == ("image", 4, 12)
    video = media_item(
        {
            "id": "2",
            "created_time": "2026-10-20T10:00:00+0000",
            "attachments": {"data": [{"type": "video_inline"}]},
        }
    )
    assert video is not None
    assert video.media_type == "video"
    album = media_item(
        {
            "id": "3",
            "created_time": "2026-10-20T10:00:00+0000",
            "attachments": {"data": [{"type": "album"}]},
        }
    )
    assert album is not None
    assert album.media_type == "carousel"
    assert media_item({"id": "4"}) is None


def test_a_comments_page_nests_replies_and_pages() -> None:
    page = comment_page(
        {
            "data": [
                {
                    "id": "c1",
                    "message": "Love it",
                    "created_time": "2026-10-20T10:00:00+0000",
                    "from": {"id": "u1", "name": "Asha"},
                    "like_count": 2,
                    "comments": {
                        "data": [
                            {
                                "id": "c2",
                                "message": "Same",
                                "created_time": "2026-10-20T11:00:00+0000",
                                "from": {"id": "u2", "name": "Ravi"},
                                "is_hidden": True,
                            }
                        ]
                    },
                },
                {"id": "c3", "message": "no author", "created_time": "2026-10-20T10:00:00+0000"},
            ],
            "paging": {"cursors": {"after": "next-1"}, "next": "https://graph/next"},
        },
        account_ref=PAGE,
        media_ref=f"{PAGE}_9",
    )
    assert [(c.platform_comment_id, c.parent_id, c.hidden) for c in page.comments] == [
        ("c1", None, False),
        ("c2", "c1", True),
    ]
    assert page.next_cursor == "next-1"


# ---------------------------------------------------------------- sending


async def test_text_goes_out_as_a_response_to_the_person() -> None:
    sent = Recorder({"recipient_id": PERSON, "message_id": "m_out_1"})
    result = await adapter(sent).send_message(account(), PERSON, OutboundMessage(text="Hello"))
    assert result.platform_message_id == "m_out_1"
    assert sent.body() == {
        "recipient": {"id": PERSON},
        "messaging_type": "RESPONSE",
        "message": {"text": "Hello"},
    }
    request = sent.requests[0]
    assert request.url.path.endswith("/me/messages")
    assert request.url.host == "graph.facebook.com"
    assert request.headers["authorization"] == "Bearer page-token"


async def test_human_agent_replies_carry_the_tag() -> None:
    sent = Recorder({"message_id": "m"})
    await adapter(sent).send_message(
        account(), PERSON, OutboundMessage(text="Hello", human_agent=True)
    )
    body = sent.body()
    assert (body["messaging_type"], body["tag"]) == ("MESSAGE_TAG", "HUMAN_AGENT")


async def test_an_attachment_is_sent_by_url_and_unsupported_ones_are_refused() -> None:
    sent = Recorder({"message_id": "m"})
    message = OutboundMessage(
        attachment=OutboundAttachment(type="image", url="https://cdn.test/a.jpg")
    )
    await adapter(sent).send_message(account(), PERSON, message)
    assert sent.body()["message"] == {
        "attachment": {
            "type": "image",
            "payload": {"url": "https://cdn.test/a.jpg", "is_reusable": False},
        }
    }
    for refused in (
        OutboundMessage(sticker="like_heart"),
        OutboundMessage(attachment=OutboundAttachment(type="sticker", url="https://cdn.test/s")),
    ):
        with pytest.raises(PlatformError) as raised:
            await adapter(sent).send_message(account(), PERSON, refused)
        assert raised.value.code == "platform_rejected"


def test_buttons_and_quick_replies_use_messengers_templates() -> None:
    buttons = text_content(
        OutboundMessage(text="Shop", buttons=(OutboundButton(title="Open", url="https://x.test"),))
    )
    assert buttons == {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": "Shop",
                "buttons": [{"type": "web_url", "url": "https://x.test", "title": "Open"}],
            },
        }
    }
    replies = text_content(
        OutboundMessage(
            text="Sure?", quick_replies=(OutboundQuickReply(title="Yes", payload="shr:1"),)
        )
    )
    assert replies == {
        "text": "Sure?",
        "quick_replies": [{"content_type": "text", "title": "Yes", "payload": "shr:1"}],
    }
    with pytest.raises(PlatformError):
        text_content(
            OutboundMessage(
                text="x",
                buttons=(OutboundButton(title="a", url="https://x.test"),),
                quick_replies=(OutboundQuickReply(title="Yes", payload="p"),),
            )
        )
    with pytest.raises(PlatformError):
        text_content(
            OutboundMessage(
                text="x" * 641, buttons=(OutboundButton(title="Open", url="https://x.test"),)
            )
        )


async def test_a_private_reply_is_addressed_by_the_comment() -> None:
    sent = Recorder({"message_id": "m_pr"})
    await adapter(sent).private_reply(account(), f"{PAGE}_9_5", OutboundMessage(text="Hi!"))
    assert sent.body()["recipient"] == {"comment_id": f"{PAGE}_9_5"}
    with pytest.raises(PlatformError):
        await adapter(sent).private_reply(
            account(),
            "c1",
            OutboundMessage(attachment=OutboundAttachment(type="image", url="https://x.test/a")),
        )
    with pytest.raises(PlatformError):
        await adapter(sent).private_reply(account(), "../../me", OutboundMessage(text="Hi"))


async def test_a_public_reply_posts_a_comment_under_the_comment() -> None:
    sent = Recorder({"id": "reply_1"})
    reply_id = await adapter(sent).reply_to_comment(account(), "c1", "Sent you a message")
    assert reply_id == "reply_1"
    assert sent.requests[0].url.path.endswith("/c1/comments")
    assert sent.query()["message"] == "Sent you a message"


async def test_hide_unhide_and_delete() -> None:
    sent = Recorder({"success": True})
    page = adapter(sent)
    await page.hide_comment(account(), "c1")
    assert sent.query()["is_hidden"] == "true"
    await page.unhide_comment(account(), "c1")
    assert sent.query()["is_hidden"] == "false"
    await page.delete_comment(account(), "c1")
    assert sent.requests[-1].method == "DELETE"
    refused = Recorder({"success": False})
    with pytest.raises(PlatformError):
        await adapter(refused).hide_comment(account(), "c1")


async def test_ice_breakers_replace_the_list_and_none_clears_it() -> None:
    sent = Recorder({"result": "success"})
    await adapter(sent).set_ice_breakers(account(), [IceBreaker("Opening hours?", "ib:1")])
    assert sent.requests[0].method == "POST"
    assert sent.requests[0].url.path.endswith("/me/messenger_profile")
    assert json.loads(sent.requests[0].content) == {
        "ice_breakers": [
            {
                "call_to_actions": [{"question": "Opening hours?", "payload": "ib:1"}],
                "locale": "default",
            }
        ]
    }
    assert sent.requests[-1].method == "GET"
    cleared = Recorder({"result": "success"})
    assert await adapter(cleared).set_ice_breakers(account(), []) == []
    assert cleared.requests[0].method == "DELETE"
    assert json.loads(cleared.requests[0].content) == {"fields": ["ice_breakers"]}


async def test_subscribing_names_the_page_fields() -> None:
    sent = Recorder({"success": True})
    await adapter(sent).subscribe_webhooks(account())
    fields = sent.query()["subscribed_fields"].split(",")
    assert {"messages", "messaging_postbacks", "messaging_referrals", "feed"} <= set(fields)
    with pytest.raises(PlatformError):
        await adapter(Recorder({"success": False})).subscribe_webhooks(account())


async def test_a_page_token_does_not_expire_so_refresh_keeps_it() -> None:
    grant = await adapter(Recorder()).refresh_token(account())
    assert (grant.access_token, grant.expires_at) == ("page-token", None)


async def test_publishing_and_insights_are_not_available_yet() -> None:
    page = adapter(Recorder())
    with pytest.raises(PlatformError) as raised:
        await page.create_image_container(account(), image_url="https://x.test/a.jpg", caption="")
    assert raised.value.code == "capability_unavailable"


def test_capabilities_have_no_publishing_and_human_agent_follows_the_setting() -> None:
    off = adapter(Recorder()).capabilities_for(account())
    assert {Capability.DM_SEND, Capability.COMMENTS, Capability.PRIVATE_REPLY} <= off
    assert not off & {Capability.PUBLISH, Capability.POST_INSIGHTS, Capability.TEMPLATES}
    assert Capability.HUMAN_AGENT not in off
    on = adapter(Recorder(), ig_human_agent_enabled=True).capabilities_for(account())
    assert Capability.HUMAN_AGENT in on


def test_the_registry_picks_the_facebook_adapter_and_the_sandbox_one_for_sandbox_pages() -> None:
    client = httpx.AsyncClient()
    deps = PlatformDeps(
        http=client, cipher=cipher_for((KEY,)), settings=settings(sandbox_platform_enabled=True)
    )
    assert isinstance(adapter_for(account(), deps), FacebookAdapter)
    sandbox = account()
    sandbox.platform_account_id = "sandbox_ab12"
    chosen = adapter_for(sandbox, deps)
    assert isinstance(chosen, SandboxAdapter)
    assert Capability.PUBLISH not in chosen.capabilities_for(sandbox)
    assert Capability.COMMENTS in chosen.capabilities_for(sandbox)


# ---------------------------------------------------------------- errors and connect


def test_messengers_closed_window_error_is_the_reply_window_error() -> None:
    body = {"error": {"code": 10, "error_subcode": 2018278, "message": "outside the window"}}
    assert map_graph_error(400, body).code == "reply_window_closed"


def test_the_authorize_url_asks_for_the_page_permissions() -> None:
    url = oauth.authorize_url(settings(), "state-1")
    parsed = urlparse(url)
    assert (parsed.netloc, parsed.path.endswith("/dialog/oauth")) == ("www.facebook.com", True)
    query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    assert query["client_id"] == "9876543210"
    assert query["state"] == "state-1"
    assert query["redirect_uri"] == "http://api.test/v1/oauth/facebook/callback"
    assert {"pages_show_list", "pages_messaging", "pages_manage_engagement"} <= set(
        query["scope"].split(",")
    )


def test_pages_are_read_with_their_tokens_and_tasks() -> None:
    pages = oauth.parse_pages(
        {
            "data": [
                {
                    "id": PAGE,
                    "name": "Maple",
                    "username": "mapleshop",
                    "access_token": "t1",
                    "tasks": ["MANAGE", "MESSAGING"],
                    "picture": {"data": {"url": "https://cdn/p.jpg"}},
                },
                {"id": "2", "name": "Moderator only", "access_token": "t2", "tasks": ["ANALYZE"]},
                {"id": "3", "name": "No token"},
            ]
        }
    )
    assert [(p.id, p.can_message) for p in pages] == [(PAGE, True), ("2", False)]
    assert pages[0].picture_url == "https://cdn/p.jpg"


# ---------------------------------------------------------------- rules a Page shares


def test_messenger_text_limit_counts_characters() -> None:
    assert sending.text_limit_error("facebook", "\U0001f600" * 2000) is None
    assert sending.text_limit_error("facebook", "a" * 2001) == (
        "Facebook messages can be up to 2,000 characters; this one is 2,001."
    )


def test_the_reply_window_has_human_agent_on_facebook_too() -> None:
    t0 = datetime(2026, 10, 24, 12, tzinfo=UTC)
    assert reply_window("facebook", t0, human_agent=False, now=t0 + timedelta(hours=23)).state == (
        "open"
    )
    closed = reply_window("facebook", t0, human_agent=False, now=t0 + timedelta(hours=25))
    assert (closed.state, may_send(closed, "human")) == ("closed", False)
    agent = reply_window("facebook", t0, human_agent=True, now=t0 + timedelta(hours=25))
    assert agent.state == "human_agent"
    assert may_send(agent, "human")
    assert not may_send(agent, "automation")


def test_an_entry_link_opens_the_pages_messenger_chat() -> None:
    assert link_url(account(), "spring26") == "https://m.me/mapleshop?ref=spring26"


# ---------------------------------------------------------------- the sandbox


def test_sandbox_events_for_a_page_parse_as_page_events() -> None:
    comment_event = parse(
        split_payload(
            _sandbox_facebook_payload(
                "sandbox_p1", SandboxInbound(account_id=_ID, kind="comment", text="price?")
            )
        )[0].payload
    )
    assert isinstance(comment_event, InboundComment)
    assert comment_event.media_id == "sandbox_p1_post_0"
    dm = parse(
        split_payload(
            _sandbox_facebook_payload(
                "sandbox_p1",
                SandboxInbound(
                    account_id=_ID, kind="dm", text="hi", quick_reply_payload="shr:1", from_id="u9"
                ),
            )
        )[0].payload
    )
    assert isinstance(dm, InboundMessage)
    assert (dm.contact_ref, dm.quick_reply_payload) == ("u9", "shr:1")
    link = parse(
        split_payload(
            _sandbox_facebook_payload(
                "sandbox_p1",
                SandboxInbound(account_id=_ID, kind="referral", referral_source="link", ref="x"),
            )
        )[0].payload
    )
    assert isinstance(link, Referral)


@pytest.mark.parametrize("kind", ["live_comment", "story_reply", "story_like", "story_mention"])
def test_sandbox_refuses_what_a_page_does_not_have(kind: str) -> None:
    body = SandboxInbound(account_id=_ID, kind=kind, text="x")  # type: ignore[arg-type]
    with pytest.raises(ApiError):
        _sandbox_facebook_payload("sandbox_p1", body)
