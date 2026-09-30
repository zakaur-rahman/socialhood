"""A fake WhatsApp Cloud API (graph.facebook.com) for respx, plus helpers to connect a number
through Embedded Signup and sign webhook deliveries with the Meta app secret."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx
import respx
from pydantic import SecretStr

from socialhood.settings import Settings
from tests.support.api import META_APP_SECRET, Clerk
from tests.support.instagram import fixture, hub_signature

GRAPH = "https://graph.facebook.com"
WABA_ID = "102290129340398"
PHONE_NUMBER_ID = "106540352242922"
BUSINESS_TOKEN = "EAAGbusiness-integration-token"
META_APP_ID = "9876543210"
WA_VERIFY_TOKEN = "fake-whatsapp-verify-token"
CUSTOMER = "919812345678"


def with_whatsapp(settings: Settings) -> Settings:
    """The API test settings plus what WhatsApp needs."""
    return settings.model_copy(
        update={
            "meta_app_id": META_APP_ID,
            "whatsapp_webhook_verify_token": SecretStr(WA_VERIFY_TOKEN),
        }
    )


def signed_delivery(body: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(body).encode()
    return raw, {
        "x-hub-signature-256": hub_signature(raw, META_APP_SECRET),
        "content-type": "application/json",
    }


def _graph(path: str) -> str:
    return rf"^{GRAPH}/v[\d.]+/{path}(\?.*)?$"


@dataclass
class FakeWhatsApp:
    """Behaviour is plain attributes, so a test changes one and the next call follows it."""

    exchange: tuple[int, dict[str, Any]] = (200, fixture("whatsapp_oauth_access_token.json"))
    number: tuple[int, dict[str, Any]] = (200, fixture("whatsapp_phone_number.json"))
    subscribe: tuple[int, dict[str, Any]] = (
        200,
        fixture("whatsapp_subscribed_apps_success.json"),
    )
    register: tuple[int, dict[str, Any]] = (200, {"success": True})
    # Found when the session info didn't name them: the shared accounts, then the numbers.
    debug_token: tuple[int, dict[str, Any]] = (200, fixture("whatsapp_debug_token.json"))
    phone_numbers: tuple[int, dict[str, Any]] = (200, fixture("whatsapp_phone_numbers.json"))
    debug_requests: list[dict[str, str]] = field(default_factory=list)  # {auth, input_token}
    pins: list[str] = field(default_factory=list)
    templates: tuple[int, dict[str, Any]] | None = None  # None: the two fixture pages
    calls: list[str] = field(default_factory=list)
    tokens_seen: list[str] = field(default_factory=list)
    exchange_params: list[dict[str, str]] = field(default_factory=list)

    def install(self, router: respx.MockRouter) -> None:
        router.get(url__regex=_graph("oauth/access_token")).mock(side_effect=self._exchange)
        router.get(url__regex=_graph("debug_token")).mock(side_effect=self._debug_token)
        router.get(url__regex=_graph(r"\d+/phone_numbers")).mock(side_effect=self._phone_numbers)
        router.get(url__regex=_graph(r"\d+")).mock(side_effect=self._number)
        router.post(url__regex=_graph(r"\d+/subscribed_apps")).mock(side_effect=self._subscribe)
        router.post(url__regex=_graph(r"\d+/register")).mock(side_effect=self._register)
        router.get(url__regex=_graph(r"\d+/message_templates")).mock(side_effect=self._templates)

    def _auth(self, request: httpx.Request) -> None:
        header = request.headers.get("authorization", "")
        if header.startswith("Bearer "):
            self.tokens_seen.append(header.removeprefix("Bearer "))

    def _exchange(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("exchange")
        self.exchange_params.append(dict(request.url.params))
        return httpx.Response(self.exchange[0], json=self.exchange[1])

    def _debug_token(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("debug_token")
        self.debug_requests.append(
            {
                "auth": request.headers.get("authorization", ""),
                "input_token": request.url.params.get("input_token", ""),
            }
        )
        return httpx.Response(self.debug_token[0], json=self.debug_token[1])

    def _phone_numbers(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("phone_numbers")
        self._auth(request)
        return httpx.Response(self.phone_numbers[0], json=self.phone_numbers[1])

    def _number(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("number")
        self._auth(request)
        body = {**self.number[1], "id": request.url.path.rsplit("/", 1)[-1]}
        return httpx.Response(self.number[0], json=body if self.number[0] < 400 else self.number[1])

    def _register(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("register")
        self.pins.append(str(json.loads(request.content)["pin"]))
        return httpx.Response(self.register[0], json=self.register[1])

    def _subscribe(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("subscribe")
        self._auth(request)
        return httpx.Response(self.subscribe[0], json=self.subscribe[1])

    def _templates(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("templates")
        self._auth(request)
        if self.templates is not None:
            return httpx.Response(self.templates[0], json=self.templates[1])
        page = 2 if request.url.params.get("after") == "QVFIUlpage2" else 1
        return httpx.Response(200, json=fixture(f"whatsapp_templates_page{page}.json"))


def install(clerk: Clerk) -> FakeWhatsApp:
    """Routes on the same respx router as the fake Clerk, so both work in one test."""
    fake = FakeWhatsApp()
    fake.install(clerk.router)
    return fake


async def signup(
    client: httpx.AsyncClient,
    clerk: Clerk,
    clerk_id: str,
    wid: str,
    *,
    code: str = "wa-code-1",
    waba_id: str | None = WABA_ID,
    phone_number_id: str | None = PHONE_NUMBER_ID,
) -> httpx.Response:
    """None leaves the id out, as when Meta's session info didn't arrive or named no number."""
    ids = {"waba_id": waba_id, "phone_number_id": phone_number_id}
    return await client.post(
        f"/v1/w/{wid}/social-accounts/whatsapp/embedded-signup",
        json={"code": code, **{k: v for k, v in ids.items() if v is not None}},
        headers=clerk.headers(clerk_id),
    )


def shared_wabas(*ids: str) -> dict[str, Any]:
    """A debug_token body whose WhatsApp scopes list these accounts."""
    body = fixture("whatsapp_debug_token.json")
    for scope in body["data"]["granular_scopes"]:
        scope["target_ids"] = list(ids)
    return body


def numbers(*ids: str) -> dict[str, Any]:
    """A phone_numbers page with these numbers."""
    return {
        "data": [
            {
                "verified_name": "Maple Bakery",
                "display_phone_number": f"+91 98765 {index:05d}",
                "id": number_id,
                "quality_rating": "GREEN",
            }
            for index, number_id in enumerate(ids)
        ]
    }
