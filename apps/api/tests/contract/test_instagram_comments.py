"""The Instagram calls comment intelligence makes (T6.1, T6.2, T6.3; FR-CMT-01, FR-CMT-04,
FR-CMT-05): a post's comments page by page with replies expanded, and hiding, showing and deleting
a comment. Shapes follow Meta's docs; docs/verification.md lists what a real account must confirm.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
import respx

from socialhood.models.connections import SocialAccount
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.instagram.adapter import InstagramAdapter
from socialhood.platforms.instagram.comments import FIELDS
from socialhood.platforms.outcome import DELIVERY_UNKNOWN
from socialhood.platforms.whatsapp.adapter import WhatsAppAdapter
from socialhood.security.crypto import TokenCipher, new_key
from socialhood.settings import AppEnv, Settings
from tests.support.instagram import GRAPH, fixture

SETTINGS = Settings(
    _env_file=None,
    app_env=AppEnv.TEST,
    database_url="postgresql+asyncpg://x/y",
    database_url_direct="postgresql://x/y",
    redis_url="redis://x",
)
BASE = f"{GRAPH}/{SETTINGS.ig_graph_version}"
TOKEN = "IGQVJcomments-token"
POST = "18100000000000003"
COMMENT = "17900000000000001"


@pytest.fixture
async def adapter() -> AsyncIterator[tuple[InstagramAdapter, SocialAccount]]:
    cipher = TokenCipher([new_key()])
    async with httpx.AsyncClient() as http:
        acct = SocialAccount(
            platform="instagram",
            platform_account_id="17841400000000001",
            username="maple.bakery",
            access_token_enc=cipher.encrypt(TOKEN),
            scopes=[],
        )
        yield InstagramAdapter(PlatformDeps(http, cipher, SETTINGS)), acct


def _authorised(route: respx.Route) -> httpx.Request:
    request = route.calls.last.request
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    assert "access_token" not in str(request.url)
    return request


# ---------------------------------------------------------------- list_comments (T6.1)


@respx.mock
async def test_a_page_of_comments_with_their_replies_and_the_next_cursor(
    adapter: tuple[InstagramAdapter, SocialAccount],
) -> None:
    ig, acct = adapter
    route = respx.get(f"{BASE}/{POST}/comments").respond(
        200, json=fixture("media_comments_page1.json")
    )

    page = await ig.list_comments(acct, POST)

    request = _authorised(route)
    assert request.url.params["fields"] == FIELDS
    assert "replies.limit(50){" in FIELDS
    assert request.url.params["limit"] == "50"
    assert "after" not in request.url.params
    assert [c.platform_comment_id for c in page.comments] == [
        "17900000000000001",
        "17900000000000002",
        "17900000000000003",
        "17900000000000004",
    ]  # the comment without an author is left out
    question, own_reply, reply, spam = page.comments
    assert (question.parent_id, reply.parent_id, own_reply.parent_id) == (None, COMMENT, COMMENT)
    assert (question.author_ref, question.author_username) == ("990000000000011", "bread.lover")
    assert question.occurred_at == datetime(2026, 9, 27, 9, 0, tzinfo=UTC)
    assert (question.media_id, question.account_ref) == (POST, "17841400000000001")
    assert (question.text, question.like_count, question.hidden) == (
        "How much is the sourdough?",
        3,
        False,
    )
    assert spam.hidden is True
    assert page.next_cursor == "QVFIUmFmdGVy"


@respx.mock
async def test_the_next_page_is_asked_for_with_the_cursor_and_the_last_has_none(
    adapter: tuple[InstagramAdapter, SocialAccount],
) -> None:
    ig, acct = adapter
    route = respx.get(f"{BASE}/{POST}/comments").respond(
        200, json=fixture("media_comments_page2.json")
    )

    page = await ig.list_comments(acct, POST, cursor="QVFIUmFmdGVy")

    assert _authorised(route).url.params["after"] == "QVFIUmFmdGVy"
    assert [c.platform_comment_id for c in page.comments] == ["17900000000000006"]
    assert page.next_cursor is None  # no "next": the last page


@respx.mock
async def test_comment_reads_refuse_a_media_id_that_is_not_one(
    adapter: tuple[InstagramAdapter, SocialAccount],
) -> None:
    ig, acct = adapter
    with pytest.raises(PlatformError) as refused:
        await ig.list_comments(acct, "../me/messages")
    assert refused.value.code == "platform_rejected"


@respx.mock
async def test_a_rate_limited_read_is_retryable(
    adapter: tuple[InstagramAdapter, SocialAccount],
) -> None:
    ig, acct = adapter
    respx.get(f"{BASE}/{POST}/comments").respond(400, json=fixture("error_4_rate_limit.json"))
    with pytest.raises(PlatformError) as limited:
        await ig.list_comments(acct, POST)
    assert (limited.value.code, limited.value.retryable) == ("platform_rate_limited", True)


# ---------------------------------------------------------------- moderation (T6.2, T6.3)


@respx.mock
@pytest.mark.parametrize(("hidden", "value"), [(True, "true"), (False, "false")])
async def test_hide_and_unhide_post_the_hide_flag(
    adapter: tuple[InstagramAdapter, SocialAccount], hidden: bool, value: str
) -> None:
    ig, acct = adapter
    route = respx.post(f"{BASE}/{COMMENT}").respond(200, json={"success": True})

    if hidden:
        await ig.hide_comment(acct, COMMENT)
    else:
        await ig.unhide_comment(acct, COMMENT)

    assert _authorised(route).url.params["hide"] == value


@respx.mock
async def test_delete_is_a_delete_on_the_comment(
    adapter: tuple[InstagramAdapter, SocialAccount],
) -> None:
    ig, acct = adapter
    route = respx.delete(f"{BASE}/{COMMENT}").respond(200, json={"success": True})
    await ig.delete_comment(acct, COMMENT)
    assert _authorised(route).method == "DELETE"


@respx.mock
async def test_deleting_a_comment_that_is_already_gone_counts_as_done(
    adapter: tuple[InstagramAdapter, SocialAccount],
) -> None:
    ig, acct = adapter
    respx.delete(f"{BASE}/{COMMENT}").respond(400, json=fixture("error_100_33_not_found.json"))
    await ig.delete_comment(acct, COMMENT)  # no error


@respx.mock
async def test_hiding_a_comment_that_is_gone_is_a_refusal(
    adapter: tuple[InstagramAdapter, SocialAccount],
) -> None:
    ig, acct = adapter
    respx.post(f"{BASE}/{COMMENT}").respond(400, json=fixture("error_100_33_not_found.json"))
    with pytest.raises(PlatformError) as refused:
        await ig.hide_comment(acct, COMMENT)
    assert (refused.value.code, refused.value.platform_code) == ("platform_rejected", "100/33")


@respx.mock
async def test_an_unconfirmed_answer_is_a_refusal(
    adapter: tuple[InstagramAdapter, SocialAccount],
) -> None:
    ig, acct = adapter
    respx.post(f"{BASE}/{COMMENT}").respond(200, json={"success": False})
    with pytest.raises(PlatformError) as refused:
        await ig.hide_comment(acct, COMMENT)
    assert refused.value.code == "platform_rejected"


@respx.mock
async def test_a_timeout_after_the_write_left_is_delivery_unknown(
    adapter: tuple[InstagramAdapter, SocialAccount],
) -> None:
    ig, acct = adapter
    respx.delete(f"{BASE}/{COMMENT}").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(PlatformError) as unknown:
        await ig.delete_comment(acct, COMMENT)
    assert (unknown.value.code, unknown.value.retryable) == (DELIVERY_UNKNOWN, False)


@respx.mock
async def test_moderation_refuses_an_id_that_is_not_one(
    adapter: tuple[InstagramAdapter, SocialAccount],
) -> None:
    ig, acct = adapter
    with pytest.raises(PlatformError):
        await ig.delete_comment(acct, "me/subscribed_apps")
    assert not respx.calls


async def test_whatsapp_has_no_comments() -> None:
    cipher = TokenCipher([new_key()])
    async with httpx.AsyncClient() as http:
        wa = WhatsAppAdapter(PlatformDeps(http, cipher, SETTINGS))
        acct = SocialAccount(platform="whatsapp", platform_account_id="1", scopes=[])
        for call in (
            wa.list_comments(acct, POST),
            wa.hide_comment(acct, COMMENT),
            wa.unhide_comment(acct, COMMENT),
            wa.delete_comment(acct, COMMENT),
        ):
            with pytest.raises(PlatformError) as refused:
                await call
            assert refused.value.code == "capability_unavailable"
