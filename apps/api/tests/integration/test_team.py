"""GR-19: team members and roles. Invite, accept, resend and revoke with a fake Clerk; the seat
limit; role changes, the owner rules, transfer and removal; the permission matrix on
representative routes; the audit log; the routes under tenancy."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.auth.invitations import FakeInvitationSender, use_invitation_sender
from tests.support.api import Clerk, sign_in
from tests.support.automation_api import Ws, set_plan, workspace
from tests.support.inbox import make_thread

PREFS = {
    "email_digest": False,
    "push": {"needs_you": True, "new_lead": True, "window_closing": True, "account": True},
}
HOURS_OFF = {"enabled": False, "days": [], "away_enabled": False, "auto_mode": "always"}


@pytest.fixture(autouse=True)
def sender() -> Iterator[FakeInvitationSender]:
    fake = FakeInvitationSender()
    with use_invitation_sender(fake):
        yield fake


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Ws:
    owner = await workspace(client, clerk)
    await set_plan(engine, owner.wid, "pro")  # three seats
    return owner


async def invite(ws: Ws, email: str, role: str = "agent", status: int = 201) -> Any:
    return await ws.ok("POST", "/invitations", status, json={"email": email, "role": role})


async def sign_in_invited(ws: Ws, email: str, **profile: Any) -> Ws:
    """The invited person signs in; /v1/me joins them to the workspace."""
    clerk_id = ws.clerk.add(email=email, **profile)
    me = await ws.client.get("/v1/me", headers=ws.clerk.headers(clerk_id))
    assert me.status_code == 200, me.text
    return Ws(ws.client, ws.clerk, clerk_id, ws.wid, me.json()["id"], ws.account_id)


async def workspace_ids(ws: Ws, person: Ws) -> list[str]:
    me = await ws.client.get("/v1/me", headers=person.headers)
    return [w["id"] for w in me.json()["workspaces"]]


async def join(ws: Ws, email: str, role: str = "agent") -> Ws:
    await invite(ws, email, role)
    person = await sign_in_invited(ws, email)
    assert ws.wid in await workspace_ids(ws, person)
    return person


# ---------------------------------------------------------------- invitations


async def test_invite_accept_and_the_role(ws: Ws, sender: FakeInvitationSender) -> None:
    created = await invite(ws, "Sam@Example.com", "agent")
    assert created["email"] == "sam@example.com"
    assert created["status"] == "pending"
    assert [m["email"] for m in sender.sent] == ["sam@example.com"]
    assert sender.sent[0]["workspace_id"] == ws.wid

    agent = await sign_in_invited(ws, "sam@example.com")
    roles = {m["email"]: m["role"] for m in (await ws.ok("GET", "/members"))["items"]}
    assert roles == {"owner@example.com": "owner", "sam@example.com": "agent"}
    assert (await ws.ok("GET", "/invitations"))["items"] == []
    me = await ws.client.get("/v1/me", headers=agent.headers)
    assert me.json()["last_workspace_id"] == ws.wid


async def test_an_unverified_email_does_not_join(ws: Ws) -> None:
    await invite(ws, "sam@example.com")
    person = await sign_in_invited(ws, "sam@example.com", verified=False)
    assert ws.wid not in await workspace_ids(ws, person)
    assert len((await ws.ok("GET", "/invitations"))["items"]) == 1


async def test_a_person_with_an_account_joins_at_next_sign_in(
    ws: Ws, sender: FakeInvitationSender, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    clerk_id, _ = await sign_in(client, clerk, email="old@example.com")
    await invite(ws, "old@example.com")
    assert sender.sent == []  # Clerk refuses a known address; they get our own email
    again = await client.get("/v1/me", headers=clerk.headers(clerk_id))
    assert ws.wid in [w["id"] for w in again.json()["workspaces"]]


async def test_an_expired_invitation_does_not_join_and_resend_renews_it(
    ws: Ws, engine: AsyncEngine
) -> None:
    created = await invite(ws, "late@example.com")
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspace_invitations SET expires_at = :t WHERE workspace_id = :w"),
            {"t": datetime.now(UTC) - timedelta(days=1), "w": ws.wid},
        )
    listed = (await ws.ok("GET", "/invitations"))["items"]
    assert [i["status"] for i in listed] == ["expired"]
    person = await sign_in_invited(ws, "late@example.com")
    assert ws.wid not in await workspace_ids(ws, person)

    renewed = await ws.ok("POST", f"/invitations/{created['id']}/resend")
    assert renewed["status"] == "pending"
    assert ws.wid in await workspace_ids(ws, person)


async def test_resend_and_revoke(ws: Ws, sender: FakeInvitationSender) -> None:
    created = await invite(ws, "sam@example.com")
    await ws.ok("POST", f"/invitations/{created['id']}/resend")
    assert len(sender.sent) == 2
    assert sender.revoked == [sender.sent[0]["id"]]  # the old link is cancelled first
    await ws.ok("DELETE", f"/invitations/{created['id']}", 204)
    assert (await ws.ok("GET", "/invitations"))["items"] == []
    assert sender.revoked[-1] == sender.sent[1]["id"]
    person = await sign_in_invited(ws, "sam@example.com")
    assert ws.wid not in await workspace_ids(ws, person)
    again = await ws.call("POST", f"/invitations/{created['id']}/resend")
    assert again.status_code == 409


async def test_duplicates_and_members_are_refused(ws: Ws) -> None:
    await invite(ws, "sam@example.com")
    await invite(ws, "SAM@example.com", status=409)
    await invite(ws, "owner@example.com", status=409)


async def test_a_failing_clerk_adds_no_invitation(ws: Ws, sender: FakeInvitationSender) -> None:
    sender.fail_next()
    await invite(ws, "sam@example.com", status=503)
    assert (await ws.ok("GET", "/invitations"))["items"] == []


async def test_only_owners_invite_admins(ws: Ws) -> None:
    admin = await join(ws, "adm@example.com", "admin")
    await invite(admin, "x@example.com", "admin", status=403)
    await invite(admin, "y@example.com", "agent")


# ---------------------------------------------------------------- seats


async def test_free_has_one_seat_and_pending_invitations_count(ws: Ws, engine: AsyncEngine) -> None:
    await set_plan(engine, ws.wid, "free")
    refused = await ws.call(
        "POST", "/invitations", json={"email": "a@example.com", "role": "agent"}
    )
    assert refused.status_code == 402
    body = refused.json()
    assert body["code"] == "quota_exceeded"
    assert body["entitlement"] == "members"
    assert body["limit"] == 1

    await set_plan(engine, ws.wid, "pro")  # the owner and two more
    await invite(ws, "a@example.com")
    await invite(ws, "b@example.com")
    seats = (await ws.ok("GET", "/members"))["seats"]
    assert seats == {"members": 1, "pending_invitations": 2, "limit": 3}
    await invite(ws, "c@example.com", status=402)
    first = (await ws.ok("GET", "/invitations"))["items"][0]
    await ws.ok("DELETE", f"/invitations/{first['id']}", 204)  # revoking frees the seat
    await invite(ws, "c@example.com")


# ---------------------------------------------------------------- members


async def test_change_role_remove_and_transfer(ws: Ws) -> None:
    sam = await join(ws, "sam@example.com", "agent")
    await ws.ok("PATCH", f"/members/{sam.user_id}", json={"role": "admin"})
    roles = {m["email"]: m["role"] for m in (await ws.ok("GET", "/members"))["items"]}
    assert roles["sam@example.com"] == "admin"

    # Admins can't change roles, remove people or move ownership.
    denied = await sam.call("PATCH", f"/members/{ws.user_id}", json={"role": "agent"})
    assert denied.status_code == 403
    assert (await sam.call("DELETE", f"/members/{ws.user_id}")).status_code == 403

    # The owner can't be demoted or removed while they are the owner.
    demote = await ws.call("PATCH", f"/members/{ws.user_id}", json={"role": "agent"})
    assert demote.status_code == 409
    assert (await ws.call("DELETE", f"/members/{ws.user_id}")).status_code == 409

    wrong = await ws.call(
        "POST", "/ownership-transfer", json={"user_id": sam.user_id, "confirm_name": "nope"}
    )
    assert wrong.status_code == 422
    name = (await ws.ok("GET", ""))["name"]
    await ws.ok("POST", "/ownership-transfer", json={"user_id": sam.user_id, "confirm_name": name})
    roles = {m["email"]: m["role"] for m in (await ws.ok("GET", "/members"))["items"]}
    assert roles == {"owner@example.com": "admin", "sam@example.com": "owner"}
    # The former owner can no longer remove the new one; the new owner removes them.
    assert (await ws.call("DELETE", f"/members/{sam.user_id}")).status_code == 403
    await sam.ok("DELETE", f"/members/{ws.user_id}", 204)
    assert (await ws.call("GET", "")).status_code == 404


async def test_removing_a_member_keeps_their_past_actions(ws: Ws) -> None:
    sam = await join(ws, "sam@example.com", "admin")
    await sam.ok("POST", "/saved-replies", 201, json={"title": "T", "shortcut": "t", "body": "Hi"})
    await ws.ok("DELETE", f"/members/{sam.user_id}", 204)
    assert (await sam.call("GET", "/members")).status_code == 404
    events = (await ws.ok("GET", "/audit-events"))["items"]
    created = [e for e in events if e["action"] == "saved_reply.created"]
    assert created
    assert created[0]["actor_user_id"] == sam.user_id
    assert created[0]["actor_name"]
    removed = [e for e in events if e["action"] == "member.removed"]
    assert removed
    assert removed[0]["target_id"] == sam.user_id


async def test_a_removed_member_can_be_invited_again(ws: Ws) -> None:
    sam = await join(ws, "sam@example.com")
    await ws.ok("DELETE", f"/members/{sam.user_id}", 204)
    await invite(ws, "sam@example.com")


# ---------------------------------------------------------------- the matrix


async def test_an_agent_replies_but_cannot_manage(ws: Ws, engine: AsyncEngine) -> None:
    agent = await join(ws, "ag@example.com", "agent")
    perms = await agent.ok("GET", "/permissions")
    assert perms["role"] == "agent"
    assert "inbox.reply" in perms["permissions"]
    assert "billing.manage" not in perms["permissions"]

    denied: list[tuple[str, str, dict[str, Any] | None]] = [
        ("POST", "/automations", {"name": "x"}),
        ("POST", "/billing/checkout", {"plan": "pro"}),
        ("POST", "/knowledge-sources", {"type": "faq", "question": "q?", "body": "a"}),
        ("PATCH", "", {"name": "Renamed"}),
        (
            "POST",
            "/webhook-endpoints",
            {"url": "https://h.example.com/x", "events": ["lead.captured"]},
        ),
        ("POST", "/saved-replies", {"title": "t", "shortcut": "t", "body": "b"}),
        ("PUT", "/business-hours", HOURS_OFF),
        ("POST", "/invitations", {"email": "q@example.com", "role": "agent"}),
        ("DELETE", "", None),
    ]
    for method, path, body in denied:
        response = await agent.call(method, path, json=body)
        assert response.status_code == 403, f"{method} {path}: {response.text}"
        assert response.json()["code"] == "forbidden"
    assert (await agent.call("GET", "/members")).status_code == 403
    assert (await agent.call("GET", "/audit-events")).status_code == 403

    # What an agent does.
    assert (await agent.call("GET", "/conversations")).status_code == 200
    assert (await agent.call("PUT", "/notification-preferences", json=PREFS)).status_code == 200
    thread = await make_thread(engine, workspace_id=ws.wid, account_id=ws.account_id)
    tagged = await agent.call("POST", "/tags", json={"name": "VIP"})
    assert tagged.status_code == 403  # creating a tag is an admin task
    assert (await agent.call("GET", f"/contacts/{thread.contact_id}")).status_code == 200


async def test_an_admin_edits_settings_but_not_billing_or_members(ws: Ws) -> None:
    admin = await join(ws, "adm@example.com", "admin")
    await admin.ok("POST", "/automations", 201, json={"name": "x"})
    await admin.ok("POST", "/saved-replies", 201, json={"title": "t", "shortcut": "t", "body": "b"})
    assert (await admin.call("POST", "/billing/checkout", json={"plan": "pro"})).status_code == 403
    assert (await admin.call("DELETE", "")).status_code == 403
    await admin.ok("GET", "/members")
    await admin.ok("GET", "/audit-events")


async def test_a_message_sent_by_a_member_is_audited_without_its_text(
    ws: Ws, engine: AsyncEngine
) -> None:
    agent = await join(ws, "ag@example.com", "agent")
    thread = await make_thread(engine, workspace_id=ws.wid, account_id=ws.account_id)
    sent = await agent.call(
        "POST",
        f"/conversations/{thread.conversation_id}/messages",
        json={"client_id": "5f0c3c1e-2d7a-4b43-9d35-9d7f0b0c2a11", "text": "Secret text body"},
        headers={"Idempotency-Key": "k1"},
    )
    assert sent.status_code == 202, sent.text
    events = (await ws.ok("GET", "/audit-events?action=message.sent"))["items"]
    assert events[0]["actor_user_id"] == agent.user_id
    assert "Secret text body" not in str(events)


# ---------------------------------------------------------------- audit


async def test_the_audit_log_filters_and_pages(ws: Ws) -> None:
    other = await join(ws, "adm@example.com", "admin")
    for i in range(3):
        await ws.ok("POST", "/automations", 201, json={"name": f"A{i}"})
    await other.ok("POST", "/saved-replies", 201, json={"title": "t", "shortcut": "t", "body": "b"})
    everything = await ws.ok("GET", "/audit-events?limit=100")
    expected = {"automation.created", "saved_reply.created", "member.invited", "member.joined"}
    assert expected <= set(everything["actions"])
    mine = await ws.ok("GET", f"/audit-events?member={other.user_id}")
    assert {e["actor_user_id"] for e in mine["items"]} == {other.user_id}
    created = await ws.ok("GET", "/audit-events?action=automation.created&limit=2")
    assert len(created["items"]) == 2
    assert created["has_more"] is True
    rest = await ws.ok("GET", "/audit-events?action=automation.created&limit=2&offset=2")
    assert len(rest["items"]) == 1
    assert rest["has_more"] is False
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert (await ws.ok("GET", "/audit-events", params={"since": future}))["items"] == []
    ordered = [e["at"] for e in everything["items"]]
    assert ordered == sorted(ordered, reverse=True)


async def test_settings_and_knowledge_changes_are_audited(ws: Ws) -> None:
    await ws.ok("PATCH", "", json={"name": "Renamed shop"})
    await ws.ok(
        "POST",
        "/knowledge-sources",
        201,
        json={"type": "faq", "question": "Hours?", "body": "Nine to five."},
    )
    actions = (await ws.ok("GET", "/audit-events"))["actions"]
    assert "settings.updated" in actions
    assert "knowledge.created" in actions
    events = (await ws.ok("GET", "/audit-events?action=knowledge.created"))["items"]
    assert "Nine to five" not in str(events)


# ---------------------------------------------------------------- tenancy


async def test_another_workspace_cannot_see_or_touch_invitations(
    ws: Ws, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    created = await invite(ws, "sam@example.com")
    other = await workspace(client, clerk, email="rival@example.com")
    assert (await other.ok("GET", "/invitations"))["items"] == []
    assert (await other.call("DELETE", f"/invitations/{created['id']}")).status_code == 404
    assert (await other.call("POST", f"/invitations/{created['id']}/resend")).status_code == 404
    cross = await client.get(f"/v1/w/{ws.wid}/members", headers=other.headers)
    assert cross.status_code == 404
