"""The caps that keep a public or free route from spending without bound: AI on website chat
messages, signed uploads naming one file, and when reconcile may trust "no such subscription"."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from socialhood.billing.dodo_fake import FakeDodo
from socialhood.billing.reconcile import dodo_key_works, too_many_missing
from socialhood.errors import ApiError
from socialhood.media.cloudinary import Cloudinary, sign
from socialhood.security.widget_tokens import VisitorClaim
from socialhood.services import media_assets
from socialhood.services.widget import chat
from socialhood.settings import AppEnv, Settings


class Windows:
    """Just enough of Valkey for ``ratelimit.hit``: counts per key, admits up to the limit."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def register_script(self, _: str) -> Callable[..., Awaitable[int]]:
        async def run(*, keys: list[str], args: list[Any]) -> int:
            used = self.counts.get(keys[0], 0)
            if used >= int(args[2]):
                return 1000
            self.counts[keys[0]] = used + 1
            return 0

        return run


def claim(visitor: str = "v_1") -> VisitorClaim:
    return VisitorClaim(uuid.uuid4(), uuid.UUID(int=1), visitor, "example.com", 0)


async def test_a_visitor_gets_ai_up_to_their_daily_cap() -> None:
    redis: Any = Windows()
    answers = [await chat._ai_allowed(redis, claim(), "agency") for _ in range(41)]
    assert answers == [True] * 40 + [False]


async def test_many_visitors_share_the_workspace_daily_cap() -> None:
    redis: Any = Windows()
    answers = [await chat._ai_allowed(redis, claim(f"v_{i}"), "free") for i in range(21)]
    assert answers == [True] * 20 + [False]


async def test_ai_is_held_back_when_the_counts_cant_be_read() -> None:
    redis: Any = Mock()
    redis.register_script.side_effect = ConnectionError("down")
    assert await chat._ai_allowed(redis, claim(), "agency") is False


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnv.TEST,
        cloudinary_cloud_name="demo",
        cloudinary_api_key="key",
        cloudinary_api_secret="secret",
    )


async def _signed(resource_type: Any, purpose: str, extension: str | None) -> Any:
    async with httpx.AsyncClient() as http:
        return await media_assets.upload_signature(
            Cloudinary(http, _settings()),
            AsyncMock(),
            uuid.uuid4(),
            purpose=purpose,
            resource_type=resource_type,
            extension=extension,
        )


async def test_each_signature_names_one_new_file_and_signs_that_name() -> None:
    first = await _signed("image", "message", None)
    second = await _signed("image", "message", None)

    assert first.public_id != second.public_id
    assert "." not in first.public_id
    params = {
        "allowed_formats": first.allowed_formats,
        "folder": first.folder,
        "public_id": first.public_id,
        "timestamp": first.timestamp,
    }
    assert first.signature == sign(params, "secret")


async def test_a_signature_names_only_the_formats_the_purpose_can_register() -> None:
    assert "html" not in (await _signed("image", "message", None)).allowed_formats
    assert "svg" not in (await _signed("video", "post", None)).allowed_formats
    raw = (await _signed("raw", "knowledge", "docx")).allowed_formats.split(",")
    assert "docx" in raw
    assert "html" not in raw


async def test_a_raw_upload_keeps_an_accepted_extension_and_refuses_others() -> None:
    assert (await _signed("raw", "knowledge", "DOCX")).public_id.endswith(".docx")
    assert (await _signed("raw", "message", "xlsx")).public_id.endswith(".xlsx")
    for purpose, extension in (("knowledge", "html"), ("knowledge", None), ("message", "html")):
        with pytest.raises(ApiError) as caught:
            await _signed("raw", purpose, extension)
        assert caught.value.code == "unsupported_media"


@pytest.mark.parametrize(
    ("missing", "checked", "too_many"),
    [(1, 1, False), (2, 2, False), (3, 3, True), (3, 6, False), (4, 6, True)],
)
def test_most_paid_subscriptions_missing_at_once_stops_the_expiry(
    missing: int, checked: int, too_many: bool
) -> None:
    assert too_many_missing(missing, checked) is too_many


async def test_the_key_check_needs_a_product_dodo_can_find() -> None:
    dodo = FakeDodo()
    settings = _settings().model_copy(update={"dodo_product_pro_monthly": "pdt_1"})

    assert await dodo_key_works(dodo, settings) is False
    dodo.add_product("pdt_1")
    assert await dodo_key_works(dodo, settings) is True
    assert await dodo_key_works(dodo, _settings()) is False
