"""scripts/connect_whatsapp_number.py: connecting a number with a token in development (Meta's
test number, which Embedded Signup can't connect), through the same path as the signup, against
the fake Graph API."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.security.crypto import TokenCipher
from socialhood.settings import AppEnv, Settings
from tests.support.api import TOKEN_KEY, Clerk, sign_in
from tests.support.whatsapp import PHONE_NUMBER_ID, WABA_ID, FakeWhatsApp, install, with_whatsapp

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "connect_whatsapp_number.py"
DEV_TOKEN = "EAAGdev-system-user-token"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("connect_whatsapp_number", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = load()


@pytest.fixture
def api_settings(api_settings: Settings) -> Settings:
    return with_whatsapp(api_settings)


@pytest.fixture
def whatsapp(clerk: Clerk) -> FakeWhatsApp:
    return install(clerk)


@pytest.fixture(autouse=True)
def token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(script.TOKEN_ENV, DEV_TOKEN)
    monkeypatch.setattr(script, "API_ROOT", tmp_path)  # never the developer's own .env


async def workspace(client: httpx.AsyncClient, clerk: Clerk, email: str = "o@example.com") -> Any:
    _, me = await sign_in(client, clerk, email=email)
    return me["workspaces"][0]


def argv(ws: str, phone_number_id: str = PHONE_NUMBER_ID) -> list[str]:
    return ["--workspace", ws, "--waba-id", WABA_ID, "--phone-number-id", phone_number_id]


async def rows(engine: AsyncEngine) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT * FROM social_accounts ORDER BY created_at"))
        return [dict(r._mapping) for r in result]


async def test_the_script_connects_the_number_like_the_signup(
    client: httpx.AsyncClient,
    clerk: Clerk,
    whatsapp: FakeWhatsApp,
    engine: AsyncEngine,
    api_settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ws = await workspace(client, clerk)
    assert await script.run(argv(ws["slug"]), settings=api_settings) == 0

    assert whatsapp.calls == ["number", "subscribe", "register"]
    assert whatsapp.tokens_seen == [DEV_TOKEN, DEV_TOKEN]
    [row] = await rows(engine)
    assert (row["platform_account_id"], row["waba_id"], row["status"]) == (
        PHONE_NUMBER_ID,
        WABA_ID,
        "active",
    )
    assert str(row["workspace_id"]) == ws["id"]
    assert row["webhooks_subscribed_at"] is not None
    assert TokenCipher([TOKEN_KEY]).decrypt(row["access_token_enc"]) == DEV_TOKEN
    out, err = capsys.readouterr()
    assert str(row["id"]) in out
    assert "+91 98765 43210" in out
    assert "status: active" in out
    assert DEV_TOKEN not in out + err

    listed = await client.get(
        f"/v1/w/{ws['id']}/social-accounts",
        headers=clerk.headers(next(iter(clerk.users))),
    )
    assert [a["platform"] for a in listed.json()["items"]] == ["whatsapp"]


async def test_a_refused_registration_still_connects_the_test_number(
    client: httpx.AsyncClient,
    clerk: Clerk,
    whatsapp: FakeWhatsApp,
    engine: AsyncEngine,
    api_settings: Settings,
) -> None:
    whatsapp.register = (400, {"error": {"code": 100, "message": "Test numbers can't register"}})
    ws = await workspace(client, clerk)
    assert await script.run(argv(ws["id"]), settings=api_settings) == 0
    [row] = await rows(engine)
    assert (row["status"], row["whatsapp_pin_enc"]) == ("active", None)


async def test_the_rules_of_the_signup_apply(
    client: httpx.AsyncClient,
    clerk: Clerk,
    whatsapp: FakeWhatsApp,
    engine: AsyncEngine,
    api_settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    a = await workspace(client, clerk, "a@example.com")
    b = await workspace(client, clerk, "b@example.com")
    assert await script.run(argv(a["slug"]), settings=api_settings) == 0
    capsys.readouterr()

    # Live in another workspace.
    assert await script.run(argv(b["slug"]), settings=api_settings) == 1
    assert "account_in_use" in capsys.readouterr().err
    # The free plan's one WhatsApp number.
    assert await script.run(argv(a["slug"], "106540352240000"), settings=api_settings) == 1
    assert "quota_exceeded" in capsys.readouterr().err
    assert [str(r["workspace_id"]) for r in await rows(engine)] == [a["id"]]


async def test_the_script_refuses_production_an_inactive_workspace_and_no_token(
    client: httpx.AsyncClient,
    clerk: Clerk,
    whatsapp: FakeWhatsApp,
    engine: AsyncEngine,
    api_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ws = await workspace(client, clerk)
    production = api_settings.model_copy(update={"app_env": AppEnv.PRODUCTION})
    assert await script.run(argv(ws["slug"]), settings=production) == 2
    assert "development only" in capsys.readouterr().err

    assert await script.run(argv("no-such-workspace"), settings=api_settings) == 2
    assert "No workspace" in capsys.readouterr().err

    async with engine.begin() as conn:
        await conn.execute(text("UPDATE workspaces SET status = 'deleting'"))
    assert await script.run(argv(ws["slug"]), settings=api_settings) == 2
    assert "isn't active" in capsys.readouterr().err

    monkeypatch.delenv(script.TOKEN_ENV)
    assert await script.run(argv(ws["slug"]), settings=api_settings) == 2
    assert script.TOKEN_ENV in capsys.readouterr().err

    assert whatsapp.calls == []
    assert await rows(engine) == []


def test_ids_must_be_numeric(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        script.parse(["--workspace", "w", "--waba-id", "me/x", "--phone-number-id", "1"])
    assert "numeric" in capsys.readouterr().err
