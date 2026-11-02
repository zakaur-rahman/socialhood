"""C-167: API key hardening. A member's keys are revoked when they leave (removed, or their account
deleted) and stop on the public API and on /mcp; ownership transfer revokes nothing. Keys may
expire (refused once expired, owners told 7 days before, once) and may carry an IP allowlist
(IPv4, IPv6 and CIDRs; 403 from elsewhere, on both surfaces), editable with the name. GitHub's
secret scanning reports revoke a leaked key only when GitHub's signature verifies. And the daily
MCP upload cleanup deletes unfinished tickets' files but never a registered one."""

from __future__ import annotations

import base64
import json
import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from socialhood.auth.invitations import FakeInvitationSender, use_invitation_sender
from socialhood.jobs.tasks.api_keys import notify_expiring
from socialhood.jobs.tasks.purge import clean_mcp_upload_tickets
from socialhood.media.cloudinary import CloudinaryError
from socialhood.media.purge import StoredFile
from socialhood.services import clerk_sync, secret_scanning
from socialhood.services.api_keys import hash_key
from socialhood.settings import Settings
from tests.support.api import Clerk
from tests.support.automation_api import Ws, set_plan, workspace
from tests.support.inbox import make_asset
from tests.support.mcp import ACCEPT, URL, http_client, rpc
from tests.support.sending import clean_outbox

SCANNING = "/v1/security/secret-scanning"
GITHUB_KEY_ID = "bcb53661c06b4728e59d897fb6165d5c9cda0fd9cdf9d09ead458168deb7518c"


@pytest.fixture
def api_settings(api_settings: Settings) -> Settings:
    """Read the caller's address from X-Forwarded-For, as production does behind Caddy."""
    return api_settings.model_copy(update={"client_ip_header": "x-forwarded-for"})


@pytest.fixture(autouse=True)
def _outbox() -> Any:
    yield from clean_outbox()


@pytest.fixture(autouse=True)
def sender() -> Iterator[FakeInvitationSender]:
    fake = FakeInvitationSender()
    with use_invitation_sender(fake):
        yield fake


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Ws:
    owner = await workspace(client, clerk)
    await set_plan(engine, owner.wid, "max")  # keys are Business (C-172); three seats
    return owner


async def join(ws: Ws, email: str, role: str = "admin") -> Ws:
    await ws.ok("POST", "/invitations", 201, json={"email": email, "role": role})
    clerk_id = ws.clerk.add(email=email)
    me = await ws.client.get("/v1/me", headers=ws.clerk.headers(clerk_id))
    assert me.status_code == 200, me.text
    return Ws(ws.client, ws.clerk, clerk_id, ws.wid, me.json()["id"], ws.account_id)


async def make_key(member: Ws, name: str = "Zapier", **body: Any) -> tuple[str, dict[str, Any]]:
    made = await member.ok(
        "POST", "/api-keys", 201, json={"name": name, "scopes": ["contacts:read"], **body}
    )
    return made["key"], made


async def public_me(
    client: httpx.AsyncClient, key: str, ip: str = "198.51.100.10"
) -> httpx.Response:
    return await client.get(
        "/public/v1/me", headers={"Authorization": f"Bearer {key}", "X-Forwarded-For": ip}
    )


async def mcp_list(app: FastAPI, key: str, ip: str = "198.51.100.10") -> httpx.Response:
    async with http_client(app, key, **{"X-Forwarded-For": ip}) as http:
        return await http.post(URL, json=rpc("tools/list", {}), headers=ACCEPT)


async def rows(engine: AsyncEngine, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in (await conn.execute(text(sql), params)).all()]


async def execute(engine: AsyncEngine, sql: str, **params: Any) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(sql), params)


# ---------------------------------------------------------------- revoked when a member leaves


async def test_a_removed_members_keys_stop_on_the_public_api_and_mcp(
    ws: Ws, mcp_app: FastAPI, engine: AsyncEngine
) -> None:
    sam = await join(ws, "sam@example.com")
    key, made = await make_key(sam, "Sam's Zapier")
    second, _ = await make_key(sam, "Sam's Claude Code")
    owners, _ = await make_key(ws, "Owner's key")
    assert (await public_me(ws.client, key)).status_code == 200
    assert (await mcp_list(mcp_app, key)).status_code == 200

    members = {m["email"]: m for m in (await ws.ok("GET", "/members"))["items"]}
    assert members["sam@example.com"]["active_api_keys"] == 2
    assert members["owner@example.com"]["active_api_keys"] == 1

    await ws.ok("DELETE", f"/members/{sam.user_id}", 204)

    for k in (key, second):
        refused = await public_me(ws.client, k)
        assert refused.status_code == 401
        assert refused.json()["detail"] == "That API key has been revoked."
        mcp = await mcp_list(mcp_app, k)
        assert mcp.status_code == 401
        assert "revoked" in mcp.headers["www-authenticate"]
    assert (await public_me(ws.client, owners)).status_code == 200  # only theirs

    events = (await ws.ok("GET", "/audit-events"))["items"]
    revoked = [e for e in events if e["action"] == "api_key.revoked"]
    assert len(revoked) == 2
    assert made["id"] in {e["target_id"] for e in revoked}
    assert all("removed from the workspace" in e["detail"]["reason"] for e in revoked)
    assert all(e["actor_user_id"] == ws.user_id for e in revoked)  # the owner who removed them
    [removal] = [e for e in events if e["action"] == "member.removed"]
    assert removal["detail"]["revoked_api_access"] == 2


async def test_moving_ownership_revokes_nothing(ws: Ws, engine: AsyncEngine) -> None:
    sam = await join(ws, "sam@example.com")
    owners, _ = await make_key(ws, "Owner's key")
    sams, _ = await make_key(sam, "Sam's key")
    name = (await ws.ok("GET", ""))["name"]
    await ws.ok("POST", "/ownership-transfer", json={"user_id": sam.user_id, "confirm_name": name})
    assert (await public_me(ws.client, owners)).status_code == 200
    assert (await public_me(ws.client, sams)).status_code == 200
    assert await rows(engine, "SELECT id FROM api_keys WHERE revoked_at IS NOT NULL") == []


async def test_deleting_an_account_revokes_its_keys_in_every_workspace(
    ws: Ws, engine: AsyncEngine, mcp_app: FastAPI
) -> None:
    sam = await join(ws, "sam@example.com")
    key, _ = await make_key(sam)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        outcome = await clerk_sync.apply_event(
            session, {"type": "user.deleted", "data": {"id": sam.clerk_id}}
        )
        await session.commit()
    assert outcome == "processed"
    assert (await public_me(ws.client, key)).json()["detail"] == "That API key has been revoked."
    assert (await mcp_list(mcp_app, key)).status_code == 401
    [event] = await rows(
        engine, "SELECT actor_label, detail FROM audit_events WHERE action = 'api_key.revoked'"
    )
    assert event["actor_label"] == "Account deleted"
    assert "deleted their account" in event["detail"]["reason"]


async def test_a_key_whose_maker_left_without_a_revocation_is_refused(
    ws: Ws, engine: AsyncEngine
) -> None:
    """Defence in depth: a membership gone some other way still stops the public API."""
    sam = await join(ws, "sam@example.com")
    key, _ = await make_key(sam)
    await execute(engine, "DELETE FROM workspace_members WHERE user_id = :u", u=sam.user_id)
    refused = await public_me(ws.client, key)
    assert refused.status_code == 401
    assert "no longer in the workspace" in refused.json()["detail"]


async def test_a_key_from_a_deleted_account_before_c167_still_works_and_is_flagged(
    ws: Ws, engine: AsyncEngine
) -> None:
    key, made = await make_key(ws)
    await execute(
        engine, "UPDATE api_keys SET created_by_user_id = NULL WHERE id = :k", k=made["id"]
    )
    assert (await public_me(ws.client, key)).status_code == 200
    [listed] = (await ws.ok("GET", "/api-keys"))["items"]
    assert listed["made_by_former_member"] is True


# ---------------------------------------------------------------- expiry


async def test_a_key_can_expire_and_is_refused_after(
    ws: Ws, engine: AsyncEngine, mcp_app: FastAPI
) -> None:
    key, made = await make_key(ws, expires_in_days=90)
    expires = datetime.fromisoformat(made["expires_at"])
    assert timedelta(days=89, hours=23) < expires - datetime.now(UTC) <= timedelta(days=90)
    never, plain = await make_key(ws, "Never")
    assert plain["expires_at"] is None
    assert (await public_me(ws.client, key)).status_code == 200

    await execute(
        engine,
        "UPDATE api_keys SET expires_at = now() - interval '1 minute' WHERE id = :k",
        k=made["id"],
    )
    refused = await public_me(ws.client, key)
    assert refused.status_code == 401
    assert refused.json()["detail"] == "That API key has expired."
    mcp = await mcp_list(mcp_app, key)
    assert mcp.status_code == 401
    assert "That API key has expired." in mcp.headers["www-authenticate"]
    assert (await public_me(ws.client, never)).status_code == 200


@pytest.mark.parametrize("days", [0, 7, 31, 1000, "30"])
async def test_only_30_90_or_365_days(ws: Ws, days: Any) -> None:
    response = await ws.call(
        "POST",
        "/api-keys",
        json={"name": "X", "scopes": ["contacts:read"], "expires_in_days": days},
    )
    assert response.status_code == 422


async def test_owners_and_admins_hear_once_a_week_before_a_key_expires(
    ws: Ws, engine: AsyncEngine
) -> None:
    sam = await join(ws, "sam@example.com", "admin")
    ana = await join(ws, "ana@example.com", "agent")
    _, soon = await make_key(ws, "Soon", expires_in_days=30)
    _, later = await make_key(ws, "Later", expires_in_days=30)
    _, gone = await make_key(ws, "Revoked", expires_in_days=30)
    await ws.ok("DELETE", f"/api-keys/{gone['id']}")
    await execute(
        engine,
        "UPDATE api_keys SET expires_at = now() + interval '6 days' WHERE id IN (:a, :b)",
        a=soon["id"],
        b=gone["id"],
    )
    await execute(
        engine,
        "UPDATE api_keys SET expires_at = now() + interval '8 days' WHERE id = :k",
        k=later["id"],
    )
    maker = async_sessionmaker(engine, expire_on_commit=False)

    told = await notify_expiring(maker)
    assert told == [uuid.UUID(soon["id"])]
    notes = await rows(
        engine, "SELECT user_id, title, link FROM notifications WHERE type = 'api_key_expiring'"
    )
    assert {str(n["user_id"]) for n in notes} == {ws.user_id, sam.user_id}  # not the agent
    assert ana.user_id not in {str(n["user_id"]) for n in notes}
    assert all("Soon" in n["title"] and n["link"] == "/settings/api-keys" for n in notes)

    assert await notify_expiring(maker) == []  # once per key
    assert (
        len(await rows(engine, "SELECT id FROM notifications WHERE type = 'api_key_expiring'")) == 2
    )


# ---------------------------------------------------------------- IP allowlist


async def test_the_allowlist_takes_ips_cidrs_and_ipv6_and_normalises_them(ws: Ws) -> None:
    _, made = await make_key(
        ws, allowed_ips=["203.0.113.7", " 10.0.0.0/8 ", "2001:DB8::/32", "203.0.113.7", "::1"]
    )
    assert made["allowed_ips"] == ["203.0.113.7", "10.0.0.0/8", "2001:db8::/32", "::1"]


@pytest.mark.parametrize(
    "entries",
    [
        ["not an ip"],
        ["10.0.0.5/8"],
        ["300.1.1.1"],
        ["10.0.0.0/33"],
        [f"10.0.0.{i}" for i in range(21)],
    ],
)
async def test_a_bad_allowlist_is_422(ws: Ws, entries: list[str]) -> None:
    response = await ws.call(
        "POST", "/api-keys", json={"name": "X", "scopes": ["contacts:read"], "allowed_ips": entries}
    )
    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    ("ip", "allowed"),
    [
        ("203.0.113.7", True),  # the single address
        ("203.0.113.8", False),
        ("192.0.2.200", True),  # inside 192.0.2.128/25
        ("192.0.2.1", False),
        ("2001:db8:1234::42", True),  # inside 2001:db8::/32
        ("2001:db9::1", False),
        ("::ffff:203.0.113.7", True),  # IPv4-mapped IPv6
        ("198.51.100.10", False),
    ],
)
async def test_the_allowlist_on_the_public_api_and_mcp(
    ws: Ws, mcp_app: FastAPI, ip: str, allowed: bool
) -> None:
    key, _ = await make_key(
        ws,
        scopes=["contacts:read", "conversations:read"],
        allowed_ips=["203.0.113.7", "192.0.2.128/25", "2001:db8::/32"],
    )
    public = await public_me(ws.client, key, ip)
    mcp = await mcp_list(mcp_app, key, ip)
    if allowed:
        assert public.status_code == 200, public.text
        assert mcp.status_code == 200, mcp.text
    else:
        assert public.status_code == 403
        assert public.json()["detail"] == "This API key can't be used from this address."
        assert mcp.status_code == 403
        assert mcp.json()["error_description"] == "This API key can't be used from this address."


async def test_the_name_and_allowlist_can_change_but_never_the_scopes(
    ws: Ws, engine: AsyncEngine
) -> None:
    key, made = await make_key(ws, allowed_ips=["203.0.113.7"])
    assert (await public_me(ws.client, key)).status_code == 403
    changed = await ws.ok(
        "PATCH",
        f"/api-keys/{made['id']}",
        json={"name": "Renamed", "allowed_ips": ["198.51.100.0/24"]},
    )
    assert changed["name"] == "Renamed"
    assert changed["allowed_ips"] == ["198.51.100.0/24"]
    assert (await public_me(ws.client, key)).status_code == 200
    cleared = await ws.ok("PATCH", f"/api-keys/{made['id']}", json={"allowed_ips": []})
    assert cleared["allowed_ips"] == []
    assert (await public_me(ws.client, key, "203.0.113.99")).status_code == 200

    scopes = await ws.call("PATCH", f"/api-keys/{made['id']}", json={"scopes": ["contacts:write"]})
    assert scopes.status_code == 422
    [event, *_] = [
        e
        for e in (await ws.ok("GET", "/audit-events"))["items"]
        if e["action"] == "api_key.updated"
    ]
    assert event["detail"]["fields"] == ["allowed_ips"]

    await ws.ok("DELETE", f"/api-keys/{made['id']}")
    revoked = await ws.call("PATCH", f"/api-keys/{made['id']}", json={"name": "Back"})
    assert revoked.status_code == 409


async def test_editing_needs_the_integrations_permission(ws: Ws) -> None:
    ana = await join(ws, "ana@example.com", "agent")
    _, made = await make_key(ws)
    denied = await ana.call("PATCH", f"/api-keys/{made['id']}", json={"name": "Mine"})
    assert denied.status_code == 403


# ---------------------------------------------------------------- GitHub secret scanning


@pytest.fixture
def github(clerk: Clerk) -> Iterator[ec.EllipticCurvePrivateKey]:
    """GitHub's signing key, served at the public keys URL (fresh cache per test)."""
    private = ec.generate_private_key(ec.SECP256R1())
    pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    clerk.router.get(secret_scanning.KEYS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "public_keys": [
                    {"key_identifier": GITHUB_KEY_ID, "key": pem.decode(), "is_current": True}
                ]
            },
        )
    )
    secret_scanning.PUBLIC_KEYS.keys.clear()
    secret_scanning.PUBLIC_KEYS.fetched_at = 0.0
    yield private
    secret_scanning.PUBLIC_KEYS.keys.clear()
    secret_scanning.PUBLIC_KEYS.fetched_at = 0.0


def signed(
    private: ec.EllipticCurvePrivateKey, body: bytes, key_id: str = GITHUB_KEY_ID
) -> dict[str, str]:
    signature = private.sign(body, ec.ECDSA(hashes.SHA256()))
    return {
        "Content-Type": "application/json",
        "Github-Public-Key-Identifier": key_id,
        "Github-Public-Key-Signature": base64.b64encode(signature).decode(),
    }


def alert_body(*tokens: str) -> bytes:
    return json.dumps(
        [
            {
                "token": token,
                "type": "amplychat_api_key",
                "url": "https://github.com/octocat/Hello-World/blob/main/.env",
                "source": "content",
            }
            for token in tokens
        ]
    ).encode()


async def test_a_signed_report_revokes_the_key_and_tells_owners_and_admins(
    ws: Ws, engine: AsyncEngine, github: ec.EllipticCurvePrivateKey
) -> None:
    key, made = await make_key(ws, "Leaked")
    body = alert_body(key)
    response = await ws.client.post(SCANNING, content=body, headers=signed(github, body))
    assert response.status_code == 200, response.text
    assert response.json() == [
        {"token_hash": hash_key(key), "token_type": "amplychat_api_key", "label": "true_positive"}
    ]
    assert (await public_me(ws.client, key)).json()["detail"] == "That API key has been revoked."
    [event] = await rows(
        engine,
        "SELECT actor_label, target_id, detail FROM audit_events WHERE action = 'api_key.revoked'",
    )
    assert event["actor_label"] == "GitHub secret scanning"
    assert event["target_id"] == made["id"]
    assert event["detail"]["reason"] == "revoked: found in a public GitHub repository"
    assert event["detail"]["url"] == "https://github.com/octocat/Hello-World/blob/main/.env"
    [note] = await rows(
        engine, "SELECT title, severity FROM notifications WHERE type = 'api_key_leaked'"
    )
    assert "Leaked" in note["title"]
    assert note["severity"] == "critical"
    assert key not in json.dumps(event["detail"]) + note["title"]

    # GitHub may report the same key again, even twice in one payload: nothing more happens.
    twice = alert_body(key, key)
    again = await ws.client.post(SCANNING, content=twice, headers=signed(github, twice))
    assert [f["label"] for f in again.json()] == ["true_positive", "true_positive"]
    assert (
        len(await rows(engine, "SELECT id FROM audit_events WHERE action = 'api_key.revoked'")) == 1
    )


@pytest.mark.parametrize("tamper", ["body", "signature", "key_id", "missing"])
async def test_a_report_github_didnt_sign_is_401_and_revokes_nothing(
    ws: Ws, engine: AsyncEngine, github: ec.EllipticCurvePrivateKey, tamper: str
) -> None:
    key, _ = await make_key(ws)
    body = alert_body(key)
    headers = signed(github, body)
    sent = body
    if tamper == "body":
        sent = body.replace(b"content", b"commit!")
    elif tamper == "signature":
        other = ec.generate_private_key(ec.SECP256R1())
        headers = signed(other, body)
    elif tamper == "key_id":
        headers = signed(github, body, key_id="unknown-key-id")
    else:
        headers = {"Content-Type": "application/json"}
    response = await ws.client.post(SCANNING, content=sent, headers=headers)
    assert response.status_code == 401
    assert "token_hash" not in response.text
    assert (await public_me(ws.client, key)).status_code == 200
    assert await rows(engine, "SELECT id FROM api_keys WHERE revoked_at IS NOT NULL") == []


async def test_a_token_that_isnt_ours_changes_nothing(
    ws: Ws, engine: AsyncEngine, github: ec.EllipticCurvePrivateKey
) -> None:
    key, _ = await make_key(ws)
    stranger = "shk_" + "A" * 43  # the right shape, no such key
    body = alert_body(stranger)
    response = await ws.client.post(SCANNING, content=body, headers=signed(github, body))
    assert response.status_code == 200
    assert response.json() == [
        {
            "token_hash": hash_key(stranger),
            "token_type": "amplychat_api_key",
            "label": "false_positive",
        }
    ]
    assert (await public_me(ws.client, key)).status_code == 200
    assert await rows(engine, "SELECT id FROM audit_events WHERE action = 'api_key.revoked'") == []
    assert await rows(engine, "SELECT id FROM notifications WHERE type = 'api_key_leaked'") == []


async def test_a_new_github_key_id_refetches_the_keys(
    ws: Ws, clerk: Clerk, github: ec.EllipticCurvePrivateKey
) -> None:
    body = alert_body("shk_" + "B" * 43)
    first = await ws.client.post(SCANNING, content=body, headers=signed(github, body))
    assert first.status_code == 200
    # GitHub rotates: a new key id the cache doesn't know is fetched (after the minute's pause).
    rotated = ec.generate_private_key(ec.SECP256R1())
    pem = rotated.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    clerk.router.get(secret_scanning.KEYS_URL).mock(
        return_value=httpx.Response(
            200, json={"public_keys": [{"key_identifier": "rotated", "key": pem.decode()}]}
        )
    )
    secret_scanning.PUBLIC_KEYS.fetched_at -= secret_scanning.REFETCH_EVERY_S + 1
    second = await ws.client.post(SCANNING, content=body, headers=signed(rotated, body, "rotated"))
    assert second.status_code == 200, second.text


def test_our_keys_match_the_pattern_github_is_given() -> None:
    import re

    from socialhood.services.api_keys import generate_key

    pattern = re.compile(r"shk_[A-Za-z0-9_-]{43}")
    for _ in range(200):
        assert pattern.fullmatch(generate_key())


# ---------------------------------------------------------------- MCP upload cleanup


@dataclass
class FakeStorage:
    """The media purger: files by tag, and what was deleted."""

    tagged: dict[str, list[StoredFile]] = field(default_factory=dict)
    deleted: list[str] = field(default_factory=list)
    fail_for: set[str] = field(default_factory=set)

    async def delete_workspace_folder(self, workspace_id: uuid.UUID) -> None:
        raise AssertionError("not used")

    async def delete_files(self, workspace_id: uuid.UUID, files: Sequence[StoredFile]) -> None:
        self.deleted.extend(f.public_id for f in files)

    async def list_tagged(self, workspace_id: uuid.UUID, tag: str) -> list[StoredFile]:
        if tag in self.fail_for:
            raise CloudinaryError("Cloudinary is down")
        return list(self.tagged.get(tag, []))


async def make_ticket(
    engine: AsyncEngine,
    wid: str,
    *,
    status: str = "waiting",
    expired_hours_ago: float = 30,
    media_asset_id: uuid.UUID | None = None,
) -> uuid.UUID:
    async with engine.begin() as conn:
        ticket_id: uuid.UUID = (
            await conn.execute(
                text(
                    "INSERT INTO mcp_uploads"
                    " (workspace_id, kind, status, media_asset_id, expires_at)"
                    " VALUES (:w, 'video', :s, :m, now() - make_interval(secs => :h * 3600))"
                    " RETURNING id"
                ),
                {"w": wid, "s": status, "m": media_asset_id, "h": expired_hours_ago},
            )
        ).scalar_one()
    return ticket_id


async def test_upload_cleanup_deletes_unfinished_files_and_leaves_registered_ones(
    ws: Ws, engine: AsyncEngine
) -> None:
    asset_id = await make_asset(engine, workspace_id=ws.wid, purpose="post", resource_type="video")
    [asset] = await rows(engine, "SELECT public_id FROM media_assets WHERE id = :a", a=asset_id)
    folder = f"ws/{ws.wid}/post"

    stale = await make_ticket(engine, ws.wid)  # never finished: its file goes
    rejected = await make_ticket(engine, ws.wid, status="rejected")
    # Registered in the library but the ticket never marked (a crash between the two): kept.
    half = await make_ticket(engine, ws.wid, status="waiting")
    done = await make_ticket(engine, ws.wid, status="uploaded", media_asset_id=asset_id)
    fresh = await make_ticket(engine, ws.wid, expired_hours_ago=2)  # not a day old yet
    down = await make_ticket(engine, ws.wid)

    storage = FakeStorage(
        tagged={
            f"mcp_upload_{stale}": [StoredFile(f"{folder}/stale", "video")],
            f"mcp_upload_{half}": [StoredFile(asset["public_id"], "video")],
            f"mcp_upload_{done}": [StoredFile(asset["public_id"], "video")],
            f"mcp_upload_{fresh}": [StoredFile(f"{folder}/fresh", "video")],
            f"mcp_upload_{down}": [StoredFile(f"{folder}/down", "video")],
        },
        fail_for={f"mcp_upload_{down}"},
    )
    counts = await clean_mcp_upload_tickets(async_sessionmaker(engine), storage)

    assert storage.deleted == [f"{folder}/stale"]
    assert counts == {"tickets": 3, "files": 1, "failed": 1}
    left = {r["id"] for r in await rows(engine, "SELECT id FROM mcp_uploads")}
    assert left == {done, fresh, down}  # stale, rejected and half are gone; down tries again
    assert rejected not in left
    assert await rows(engine, "SELECT id FROM media_assets WHERE id = :a", a=asset_id)

    # The next run, with storage back, finishes the one that failed.
    storage.fail_for.clear()
    again = await clean_mcp_upload_tickets(async_sessionmaker(engine), storage)
    assert again["tickets"] == 1
    assert storage.deleted == [f"{folder}/stale", f"{folder}/down"]


async def test_upload_cleanup_stays_in_each_tickets_workspace(
    ws: Ws, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    other = await workspace(client, clerk, email="other@example.com")
    ticket = await make_ticket(engine, other.wid)
    seen: list[uuid.UUID] = []

    class Recording(FakeStorage):
        async def list_tagged(self, workspace_id: uuid.UUID, tag: str) -> list[StoredFile]:
            seen.append(workspace_id)
            return []

    await clean_mcp_upload_tickets(async_sessionmaker(engine, class_=AsyncSession), Recording())
    assert seen == [uuid.UUID(other.wid)]
    assert await rows(engine, "SELECT id FROM mcp_uploads WHERE id = :t", t=ticket) == []
