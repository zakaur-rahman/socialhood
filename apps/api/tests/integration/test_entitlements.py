"""Every plan gate in §2.15 answers 402 with its code, the §1.7 key and the limit (T8.1;
TR-BIL-04, FR-BIL-05, FR-BIL-07, errors.PlanLimit), so the upgrade dialog can name the limit.
One test per gate, on the Free plan; plus the read-only accounts of a downgrade and the two
FastAPI dependency forms."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

import httpx
import pytest
from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.auth.deps import WorkspaceContext
from socialhood.billing.entitlements import require_capacity, require_entitlement
from socialhood.settings import Settings
from tests.support.ai import make_source
from tests.support.analysis import use_credits
from tests.support.api import Clerk
from tests.support.automation_api import Ws, set_plan, workspace
from tests.support.automations import make_automation
from tests.support.inbox import make_account, make_scheduled, make_thread
from tests.support.publishing_api import Shop, iso, later, open_shop
from tests.support.whatsapp import PHONE_NUMBER_ID, WABA_ID, with_whatsapp


@pytest.fixture
def api_settings(api_settings: Settings) -> Settings:
    return with_whatsapp(api_settings)


@pytest.fixture
async def shop(app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Shop:
    """A Free workspace's owner with one Instagram account."""
    return await open_shop(app, client, clerk, engine)


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    """A Free workspace's owner with a sandbox Instagram account (the automation editor's)."""
    return await workspace(client, clerk)


def assert_402(response: httpx.Response, code: str, key: str, limit: int | None) -> dict[str, Any]:
    assert response.status_code == 402, response.text
    body: dict[str, Any] = response.json()
    assert (body["code"], body["entitlement"], body["limit"]) == (code, key, limit)
    return body


async def spend_credits(shop: Shop) -> None:
    await use_credits(shop.engine, uuid.UUID(shop.wid), 200, now=datetime.now(UTC))


async def thread(shop: Shop, account_id: uuid.UUID | None = None) -> uuid.UUID:
    made = await make_thread(
        shop.engine, workspace_id=shop.wid, account_id=account_id or shop.account_id
    )
    return made.conversation_id


# ---------------------------------------------------------------- accounts_per_platform


async def test_connecting_a_second_instagram_account(shop: Shop) -> None:
    response = await shop.call("POST", "/social-accounts/instagram/connect")
    body = assert_402(response, "quota_exceeded", "accounts_per_platform", 1)
    assert body["detail"] == "Your plan includes 1 Instagram account."


async def test_connecting_a_second_whatsapp_number(shop: Shop) -> None:
    await make_account(shop.engine, shop.wid, platform="whatsapp", platform_account_id="1234567")
    response = await shop.call(
        "POST",
        "/social-accounts/whatsapp/embedded-signup",
        {"code": "wa-code", "waba_id": WABA_ID, "phone_number_id": PHONE_NUMBER_ID},
    )
    body = assert_402(response, "quota_exceeded", "accounts_per_platform", 1)
    assert body["detail"] == "Your plan includes 1 WhatsApp account."


# ---------------------------------------------------------------- ai_modes


async def test_auto_mode_on_an_account(shop: Shop) -> None:
    response = await shop.call("PATCH", f"/social-accounts/{shop.account_id}", {"ai_mode": "auto"})
    body = assert_402(response, "entitlement_required", "ai_modes", None)
    assert body["detail"] == "Auto mode is part of Pro."
    assert (
        await shop.call("PATCH", f"/social-accounts/{shop.account_id}", {"ai_mode": "off"})
    ).status_code == 200


async def test_auto_mode_on_a_conversation(shop: Shop) -> None:
    conversation = await thread(shop)
    response = await shop.call(
        "PATCH", f"/conversations/{conversation}", {"ai_mode_override": "auto"}
    )
    assert_402(response, "entitlement_required", "ai_modes", None)


# ---------------------------------------------------------------- credits (ai_credits_monthly)


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/ai/caption", {"brief": "Sourdough is back"}),
        ("/ai/hashtags", {"caption": "Sourdough is back"}),
        ("/knowledge/test", {"question": "Do you ship to Pune?"}),
    ],
)
async def test_features_that_cost_credits(shop: Shop, path: str, body: dict[str, Any]) -> None:
    await spend_credits(shop)
    response = await shop.call("POST", path, body)
    problem = assert_402(response, "quota_exceeded", "ai_credits_monthly", 200)
    assert problem["detail"].startswith("You've used all 200 AI credits for this month.")


@pytest.mark.parametrize("action", ["suggestions", "summary"])
async def test_conversation_ai_that_costs_credits(shop: Shop, action: str) -> None:
    conversation = await thread(shop)
    await shop.execute("UPDATE social_accounts SET ai_mode = 'suggest'")
    await spend_credits(shop)
    response = await shop.call("POST", f"/conversations/{conversation}/{action}")
    assert_402(response, "quota_exceeded", "ai_credits_monthly", 200)


@pytest.mark.usefixtures("queue")
async def test_credits_are_checked_at_the_cost_of_the_feature(shop: Shop) -> None:
    """A summary costs 1 credit and knowledge tests 1 (§1.7): with 1 left, a summary is
    queued; with none left, it is refused. Its other checks still come first (analysis off is
    409 whatever the credits)."""
    conversation = await thread(shop)
    await use_credits(shop.engine, uuid.UUID(shop.wid), 199, now=datetime.now(UTC))
    assert (await shop.call("POST", f"/conversations/{conversation}/summary")).status_code == 202
    await spend_credits(shop)
    assert_402(
        await shop.call("POST", f"/conversations/{conversation}/summary"),
        "quota_exceeded",
        "ai_credits_monthly",
        200,
    )
    await shop.execute("UPDATE social_accounts SET ai_analysis_enabled = false")
    off = await shop.call("POST", f"/conversations/{conversation}/summary")
    assert (off.status_code, off.json()["code"]) == (409, "conflict")


# ---------------------------------------------------------------- pending_scheduled_messages


async def test_scheduling_past_the_pending_messages(shop: Shop) -> None:
    conversation = await thread(shop)
    for _ in range(20):
        await make_scheduled(shop.engine, workspace_id=shop.wid, conversation_id=conversation)
    response = await shop.call(
        "POST",
        f"/conversations/{conversation}/scheduled-messages",
        {"text": "Your order ships today", "send_at": iso(later(minutes=10))},
    )
    body = assert_402(response, "quota_exceeded", "pending_scheduled_messages", 20)
    assert body["detail"] == "Your plan includes 20 scheduled messages."


# ---------------------------------------------------------------- knowledge_characters


async def test_knowledge_past_the_characters(shop: Shop) -> None:
    await make_source(shop.engine, workspace_id=shop.wid, char_count=199_990)
    response = await shop.call(
        "POST",
        "/knowledge-sources",
        {"type": "faq", "question": "Do you ship?", "body": "Yes, across India."},
    )
    assert_402(response, "quota_exceeded", "knowledge_characters", 200_000)


# ---------------------------------------------------------------- automations


async def test_activating_an_ai_reply_automation(ws: Ws) -> None:
    draft = await ws.draft(
        action="ai_reply", message_text=None, message_buttons=[], ai_instructions="Be brief."
    )
    response = await ws.call("POST", f"/automations/{draft['id']}/activate")
    body = assert_402(response, "entitlement_required", "ai_reply_automations", None)
    assert body["detail"] == "AI replies in automations are part of Pro."


async def test_activating_past_the_active_automations(ws: Ws, engine: AsyncEngine) -> None:
    for word in ("one", "two", "three"):
        await make_automation(
            engine, workspace_id=ws.wid, account_id=ws.account_id, keywords=(word,)
        )
    draft = await ws.draft()
    response = await ws.call("POST", f"/automations/{draft['id']}/activate")
    body = assert_402(response, "quota_exceeded", "active_automations", 3)
    assert body["detail"] == "Your plan includes 3 active automations."


# ---------------------------------------------------------------- scheduled_posts_monthly


@pytest.mark.parametrize("action", ["schedule", "publish-now"])
async def test_publishing_past_the_scheduled_posts(shop: Shop, action: str) -> None:
    await shop.scheduled()  # makes the period's counter
    await shop.execute(
        "UPDATE usage_counters SET used = 10"
        " WHERE metric = 'scheduled_posts' AND workspace_id = :w",
        w=shop.wid,
    )
    post = await shop.ready_draft()
    body = {"publish_at": iso(later(days=1))} if action == "schedule" else None
    response = await shop.call("POST", f"/scheduled-posts/{post['id']}/{action}", body)
    problem = assert_402(response, "quota_exceeded", "scheduled_posts_monthly", 10)
    assert problem["detail"] == "Your plan includes 10 scheduled posts a month."


# ---------------------------------------------------------------- read-only accounts (FR-BIL-07)


async def test_an_account_over_the_plan_is_read_only(shop: Shop, engine: AsyncEngine) -> None:
    """After a downgrade, accounts past accounts_per_platform can't send (scheduled messages,
    automations); the earliest connected keeps the plan's slot, and Pro lifts the limit."""
    extra = await shop.account("maple.cakes")
    await shop.execute(
        "UPDATE social_accounts SET connected_at = now() + interval '1 minute' WHERE id = :a",
        a=extra,
    )
    later_message = {"text": "Your order ships today", "send_at": iso(later(minutes=10))}

    conversation = await thread(shop, extra)
    path = f"/conversations/{conversation}/scheduled-messages"
    body = assert_402(
        await shop.call("POST", path, later_message),
        "quota_exceeded",
        "accounts_per_platform",
        1,
    )
    assert body["detail"] == (
        "Your plan includes 1 Instagram account. @maple.cakes is read-only until you upgrade "
        "or disconnect another."
    )

    first = f"/conversations/{await thread(shop)}/scheduled-messages"
    assert (await shop.call("POST", first, later_message)).status_code == 201
    await set_plan(engine, shop.wid, "pro")
    assert (await shop.call("POST", path, later_message)).status_code == 201


async def test_an_automation_of_a_read_only_account_cannot_activate(
    ws: Ws, engine: AsyncEngine
) -> None:
    extra = await make_account(engine, ws.wid, username="maple.cakes")
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE social_accounts SET connected_at = now() + interval '1 minute'"
                " WHERE id = :a"
            ),
            {"a": extra},
        )
    draft = await ws.draft(social_account_id=str(extra))
    response = await ws.call("POST", f"/automations/{draft['id']}/activate")
    assert_402(response, "quota_exceeded", "accounts_per_platform", 1)


# ---------------------------------------------------------------- the dependency forms


async def test_require_entitlement_and_require_capacity_gate_a_route(
    app: FastAPI, shop: Shop
) -> None:
    async def auto_only(
        ctx: Annotated[WorkspaceContext, Depends(require_entitlement("ai_modes", "auto"))],
    ) -> dict[str, bool]:
        return {"ok": True}

    async def one_more_automation(
        ctx: Annotated[WorkspaceContext, Depends(require_capacity("active_automations"))],
    ) -> dict[str, bool]:
        return {"ok": True}

    app.router.add_api_route("/v1/w/{wid}/_gate/auto", auto_only, methods=["GET"])
    app.router.add_api_route("/v1/w/{wid}/_gate/automation", one_more_automation, methods=["GET"])

    assert_402(await shop.call("GET", "/_gate/auto"), "entitlement_required", "ai_modes", None)
    assert (await shop.call("GET", "/_gate/automation")).status_code == 200
    for word in ("one", "two", "three"):
        await make_automation(
            shop.engine, workspace_id=shop.wid, account_id=shop.account_id, keywords=(word,)
        )
    assert_402(
        await shop.call("GET", "/_gate/automation"), "quota_exceeded", "active_automations", 3
    )
    await set_plan(shop.engine, shop.wid, "pro")
    assert (await shop.call("GET", "/_gate/auto")).json() == {"ok": True}
    assert (await shop.call("GET", "/_gate/automation")).status_code == 200
    other = await shop.client.get(f"/v1/w/{uuid.uuid4()}/_gate/auto", headers=shop.headers)
    assert other.status_code == 404  # the role check runs first
