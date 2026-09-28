"""WhatsApp Cloud API calls against recorded-shape fixtures (TR-TEST-01 contract layer): Embedded
Signup, sends (text, media, templates), read receipts, media download, templates and errors."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import respx

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import OutboundAttachment, OutboundMessage, OutboundTemplate
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.events import InboundMediaRef
from socialhood.platforms.registry import adapter_for
from socialhood.platforms.whatsapp import signup
from socialhood.platforms.whatsapp.adapter import WhatsAppAdapter
from socialhood.platforms.whatsapp.graph import WhatsAppHttp
from socialhood.security.crypto import TokenCipher, new_key
from socialhood.settings import AppEnv, Settings
from tests.support.instagram import fixture
from tests.support.whatsapp import (
    BUSINESS_TOKEN,
    CUSTOMER,
    GRAPH,
    META_APP_ID,
    PHONE_NUMBER_ID,
    WABA_ID,
)

SETTINGS = Settings(
    _env_file=None,
    app_env=AppEnv.TEST,
    database_url="postgresql+asyncpg://x/y",
    database_url_direct="postgresql://x/y",
    redis_url="redis://x",
    meta_app_id=META_APP_ID,
    meta_app_secret="meta-secret",
)
V = f"{GRAPH}/{SETTINGS.meta_graph_version}"
MESSAGES = f"{V}/{PHONE_NUMBER_ID}/messages"
WAMID = "wamid.OUTBOUND000000000000000000000000000000001"
IMAGE_URL = "https://res.cloudinary.com/demo/image/upload/ws/1/message/cake.jpg"


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def cipher() -> TokenCipher:
    return TokenCipher([new_key()])


@pytest.fixture
def adapter(http: httpx.AsyncClient, cipher: TokenCipher) -> WhatsAppAdapter:
    return WhatsAppAdapter(PlatformDeps(http, cipher, SETTINGS))


@pytest.fixture
def acct(cipher: TokenCipher) -> SocialAccount:
    return SocialAccount(
        platform="whatsapp",
        platform_account_id=PHONE_NUMBER_ID,
        waba_id=WABA_ID,
        access_token_enc=cipher.encrypt(BUSINESS_TOKEN),
    )


def sent(route: respx.Route) -> Any:
    request = route.calls.last.request
    assert request.headers["authorization"] == f"Bearer {BUSINESS_TOKEN}"
    assert "access_token" not in str(request.url)
    return json.loads(request.content)


# ---------------------------------------------------------------- Embedded Signup


@respx.mock
async def test_the_code_becomes_a_business_token(http: httpx.AsyncClient) -> None:
    route = respx.get(f"{V}/oauth/access_token").respond(
        200, json=fixture("whatsapp_oauth_access_token.json")
    )
    grant = await signup.exchange_code(WhatsAppHttp(http, SETTINGS), SETTINGS, "the-code")
    assert grant.access_token == BUSINESS_TOKEN
    assert grant.expires_at is None  # business tokens don't expire unless Meta says so
    params = route.calls.last.request.url.params
    assert dict(params) == {
        "client_id": META_APP_ID,
        "client_secret": "meta-secret",
        "code": "the-code",
    }


@respx.mock
async def test_an_expiring_token_keeps_its_expiry(http: httpx.AsyncClient) -> None:
    respx.get(f"{V}/oauth/access_token").respond(
        200, json={"access_token": "t", "expires_in": 5184000}
    )
    grant = await signup.exchange_code(WhatsAppHttp(http, SETTINGS), SETTINGS, "c")
    assert grant.expires_at is not None


@respx.mock
async def test_no_token_is_an_error(http: httpx.AsyncClient) -> None:
    respx.get(f"{V}/oauth/access_token").respond(200, json={"token_type": "bearer"})
    with pytest.raises(PlatformError) as caught:
        await signup.exchange_code(WhatsAppHttp(http, SETTINGS), SETTINGS, "c")
    assert caught.value.code == "platform_rejected"


@respx.mock
async def test_the_numbers_details(http: httpx.AsyncClient) -> None:
    route = respx.get(f"{V}/{PHONE_NUMBER_ID}").respond(
        200, json=fixture("whatsapp_phone_number.json")
    )
    number = await signup.phone_number(
        WhatsAppHttp(http, SETTINGS), BUSINESS_TOKEN, PHONE_NUMBER_ID
    )
    assert (number.id, number.verified_name, number.display_phone_number) == (
        PHONE_NUMBER_ID,
        "Maple Bakery",
        "+91 98765 43210",
    )
    request = route.calls.last.request
    assert request.url.params["fields"] == "display_phone_number,verified_name,quality_rating"
    assert request.headers["authorization"] == f"Bearer {BUSINESS_TOKEN}"


@respx.mock
async def test_subscribing_the_app_to_the_business_account(
    adapter: WhatsAppAdapter, acct: SocialAccount
) -> None:
    route = respx.post(f"{V}/{WABA_ID}/subscribed_apps").respond(
        200, json=fixture("whatsapp_subscribed_apps_success.json")
    )
    await adapter.subscribe_webhooks(acct)
    assert route.calls.last.request.headers["authorization"] == f"Bearer {BUSINESS_TOKEN}"

    respx.post(f"{V}/{WABA_ID}/subscribed_apps").respond(200, json={"success": False})
    with pytest.raises(PlatformError) as caught:
        await adapter.subscribe_webhooks(acct)
    assert caught.value.code == "platform_rejected"


def test_capabilities_and_registry(
    http: httpx.AsyncClient, cipher: TokenCipher, acct: SocialAccount
) -> None:
    found = adapter_for(acct, PlatformDeps(http, cipher, SETTINGS))
    assert isinstance(found, WhatsAppAdapter)
    assert found.capabilities_for(acct) == {
        Capability.DM_SEND,
        Capability.DM_ATTACHMENTS,
        Capability.READ_RECEIPTS,
        Capability.TEMPLATES,
    }


async def test_what_whatsapp_does_not_have(adapter: WhatsAppAdapter, acct: SocialAccount) -> None:
    assert await adapter.fetch_contact_profile(acct, CUSTOMER) is None
    assert await adapter.list_media(acct) == []
    assert await adapter.list_threads(acct) == []
    with pytest.raises(PlatformError) as caught:
        await adapter.refresh_token(acct)
    assert caught.value.code == "account_needs_reconnect"


# ---------------------------------------------------------------- sending


@pytest.mark.parametrize(
    ("message", "content"),
    [
        (
            OutboundMessage(text="Yes, we ship to Pune"),
            {"type": "text", "text": {"body": "Yes, we ship to Pune", "preview_url": False}},
        ),
        (
            OutboundMessage(attachment=OutboundAttachment(type="image", url=IMAGE_URL)),
            {"type": "image", "image": {"link": IMAGE_URL}},
        ),
        (
            OutboundMessage(
                text="The blue one", attachment=OutboundAttachment(type="image", url=IMAGE_URL)
            ),
            {"type": "image", "image": {"link": IMAGE_URL, "caption": "The blue one"}},
        ),
        (
            OutboundMessage(attachment=OutboundAttachment(type="video", url="https://v/1.mp4")),
            {"type": "video", "video": {"link": "https://v/1.mp4"}},
        ),
        (
            OutboundMessage(attachment=OutboundAttachment(type="audio", url="https://a/1.ogg")),
            {"type": "audio", "audio": {"link": "https://a/1.ogg"}},
        ),
        (
            OutboundMessage(
                text="Your invoice",
                attachment=OutboundAttachment(
                    type="file", url="https://d/inv.pdf", filename="invoice-1042.pdf"
                ),
            ),
            {
                "type": "document",
                "document": {
                    "link": "https://d/inv.pdf",
                    "caption": "Your invoice",
                    "filename": "invoice-1042.pdf",
                },
            },
        ),
        (
            OutboundMessage(
                template=OutboundTemplate(
                    name="order_update", language="en", params=("Priya", "1042")
                )
            ),
            {
                "type": "template",
                "template": {
                    "name": "order_update",
                    "language": {"code": "en"},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": "Priya"},
                                {"type": "text", "text": "1042"},
                            ],
                        }
                    ],
                },
            },
        ),
        (
            OutboundMessage(attachment=OutboundAttachment(type="sticker", url="https://s/1.webp")),
            {"type": "sticker", "sticker": {"link": "https://s/1.webp"}},
        ),
        (
            OutboundMessage(template=OutboundTemplate(name="hello_again", language="en_US")),
            {
                "type": "template",
                "template": {"name": "hello_again", "language": {"code": "en_US"}},
            },
        ),
    ],
    ids=[
        "text",
        "image",
        "image-caption",
        "video",
        "audio",
        "document",
        "template",
        "sticker",
        "no-params",
    ],
)
@respx.mock
async def test_each_send_shape(
    adapter: WhatsAppAdapter, acct: SocialAccount, message: OutboundMessage, content: Any
) -> None:
    route = respx.post(MESSAGES).respond(200, json=fixture("whatsapp_send_success.json"))
    result = await adapter.send_message(acct, CUSTOMER, message)
    assert result.platform_message_id == WAMID
    assert sent(route) == {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": CUSTOMER,
        **content,
    }


@pytest.mark.parametrize(
    "message",
    [
        OutboundMessage(),
        OutboundMessage(text="hi", attachment=OutboundAttachment(type="audio", url="https://a")),
        OutboundMessage(text="hi", attachment=OutboundAttachment(type="sticker", url="https://s")),
        OutboundMessage(sticker="like_heart"),
    ],
    ids=["empty", "captioned-audio", "captioned-sticker", "heart"],
)
@respx.mock
async def test_sends_whatsapp_cannot_take_are_refused_before_calling(
    adapter: WhatsAppAdapter, acct: SocialAccount, message: OutboundMessage
) -> None:
    route = respx.post(MESSAGES)
    with pytest.raises(PlatformError) as caught:
        await adapter.send_message(acct, CUSTOMER, message)
    assert caught.value.code == "platform_rejected"
    assert not route.called


@pytest.mark.parametrize(
    ("status", "name", "code", "retryable", "platform_code"),
    [
        (400, "whatsapp_error_131047.json", "reply_window_closed", False, "131047"),
        (400, "whatsapp_error_131026.json", "recipient_unavailable", False, "131026"),
        (400, "whatsapp_error_130429.json", "platform_rate_limited", True, "130429"),
        (401, "error_190_expired.json", "account_needs_reconnect", False, "190/463"),
        (500, None, "platform_unavailable", True, None),
    ],
)
@respx.mock
async def test_send_errors_map_to_our_codes(
    adapter: WhatsAppAdapter,
    acct: SocialAccount,
    status: int,
    name: str | None,
    code: str,
    retryable: bool,
    platform_code: str | None,
) -> None:
    respx.post(MESSAGES).respond(status, json=fixture(name) if name else None)
    with pytest.raises(PlatformError) as caught:
        await adapter.send_message(acct, CUSTOMER, OutboundMessage(text="hi"))
    error = caught.value
    assert (error.code, error.retryable, error.platform_code) == (code, retryable, platform_code)


async def test_no_stored_token_asks_for_reconnect(
    adapter: WhatsAppAdapter, acct: SocialAccount
) -> None:
    acct.access_token_enc = None
    with pytest.raises(PlatformError) as caught:
        await adapter.send_message(acct, CUSTOMER, OutboundMessage(text="hi"))
    assert caught.value.code == "account_needs_reconnect"


# ---------------------------------------------------------------- read receipts


@respx.mock
async def test_mark_read_names_the_message(adapter: WhatsAppAdapter, acct: SocialAccount) -> None:
    route = respx.post(MESSAGES).respond(200, json=fixture("whatsapp_mark_read_success.json"))
    await adapter.mark_read(acct, CUSTOMER, message_ref=WAMID)
    await adapter.mark_read(acct, WAMID)
    expected = {"messaging_product": "whatsapp", "status": "read", "message_id": WAMID}
    assert [json.loads(c.request.content) for c in route.calls] == [expected, expected]


@respx.mock
async def test_mark_read_without_a_message_id_does_nothing(
    adapter: WhatsAppAdapter, acct: SocialAccount
) -> None:
    route = respx.post(MESSAGES)
    await adapter.mark_read(acct, CUSTOMER)
    assert not route.called


# ---------------------------------------------------------------- media download


@respx.mock
async def test_media_is_fetched_by_id_then_url(
    adapter: WhatsAppAdapter, acct: SocialAccount
) -> None:
    lookup = respx.get(f"{V}/1003383421387256").respond(
        200, json=fixture("whatsapp_media_url.json")
    )
    media_url = fixture("whatsapp_media_url.json")["url"]
    download = respx.get(media_url).respond(
        200, content=b"\xff\xd8jpeg-bytes", headers={"content-type": "image/jpeg"}
    )
    result = await adapter.download_media(
        acct, InboundMediaRef(kind="image", media_id="1003383421387256")
    )
    assert (result.content, result.mime_type) == (b"\xff\xd8jpeg-bytes", "image/jpeg")
    for route in (lookup, download):
        assert route.calls.last.request.headers["authorization"] == f"Bearer {BUSINESS_TOKEN}"


@respx.mock
async def test_an_expired_media_url_is_an_error(
    adapter: WhatsAppAdapter, acct: SocialAccount
) -> None:
    respx.get(f"{V}/1003383421387256").respond(200, json=fixture("whatsapp_media_url.json"))
    respx.get(fixture("whatsapp_media_url.json")["url"]).respond(404, text="Not found")
    with pytest.raises(PlatformError) as caught:
        await adapter.download_media(
            acct, InboundMediaRef(kind="image", media_id="1003383421387256")
        )
    assert caught.value.code == "platform_rejected"


@respx.mock
async def test_a_slow_media_server_is_retryable(
    adapter: WhatsAppAdapter, acct: SocialAccount
) -> None:
    respx.get(f"{V}/1003383421387256").respond(200, json=fixture("whatsapp_media_url.json"))
    respx.get(fixture("whatsapp_media_url.json")["url"]).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(PlatformError) as caught:
        await adapter.download_media(
            acct, InboundMediaRef(kind="image", media_id="1003383421387256")
        )
    assert (caught.value.code, caught.value.retryable) == ("platform_unavailable", True)


async def test_media_without_an_id_is_refused(
    adapter: WhatsAppAdapter, acct: SocialAccount
) -> None:
    with pytest.raises(PlatformError):
        await adapter.download_media(acct, InboundMediaRef(kind="image", url="https://x"))


# ---------------------------------------------------------------- templates


@respx.mock
async def test_templates_are_approved_and_sendable_with_body_params(
    adapter: WhatsAppAdapter, acct: SocialAccount
) -> None:
    def page(request: httpx.Request) -> httpx.Response:
        number = 2 if request.url.params.get("after") == "QVFIUlpage2" else 1
        return httpx.Response(200, json=fixture(f"whatsapp_templates_page{number}.json"))

    route = respx.get(f"{V}/{WABA_ID}/message_templates").mock(side_effect=page)
    templates = await adapter.list_templates(acct)

    assert [(t.name, t.language, t.category, t.param_count) for t in templates] == [
        ("hello_again", "en_US", "marketing", 0),
        ("order_update", "en", "utility", 2),
        ("order_update", "hi", "utility", 2),
    ]
    assert templates[1].body == "Hi {{1}}, your order {{2}} is on its way."
    assert {t.status for t in templates} == {"approved"}
    first, second = (c.request.url.params for c in route.calls)
    assert first["fields"] == "name,language,status,category,components"
    assert "after" not in first
    assert second["after"] == "QVFIUlpage2"
