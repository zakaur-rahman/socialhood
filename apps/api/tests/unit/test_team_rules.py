"""GR-19: the permission matrix, seat counting, invitation states, audit detail and the fake
Clerk sender."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from socialhood.auth.invitations import FakeInvitationSender, InvitationError
from socialhood.auth.permissions import (
    INVITABLE_ROLES,
    ROLE_PERMISSIONS,
    Permission,
    has_permission,
    permissions_of,
)
from socialhood.billing.plans import entitlement
from socialhood.models.identity import Role
from socialhood.services.audit import clean_detail
from socialhood.services.team import effective_status, may_invite, seat_check

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


def test_each_role_has_the_roles_below_it() -> None:
    assert (
        ROLE_PERMISSIONS[Role.AGENT] < ROLE_PERMISSIONS[Role.ADMIN] < ROLE_PERMISSIONS[Role.OWNER]
    )


def test_every_permission_belongs_to_the_owner() -> None:
    assert set(Permission) == set(ROLE_PERMISSIONS[Role.OWNER])


@pytest.mark.parametrize(
    ("role", "permission", "allowed"),
    [
        (Role.AGENT, Permission.REPLY, True),
        (Role.AGENT, Permission.TAG, True),
        (Role.AGENT, Permission.ASSIGN, True),
        (Role.AGENT, Permission.AUTOMATIONS_MANAGE, False),
        (Role.AGENT, Permission.KNOWLEDGE_MANAGE, False),
        (Role.AGENT, Permission.SETTINGS_MANAGE, False),
        (Role.AGENT, Permission.BILLING_MANAGE, False),
        (Role.AGENT, Permission.AUDIT_READ, False),
        (Role.ADMIN, Permission.AUTOMATIONS_MANAGE, True),
        (Role.ADMIN, Permission.SETTINGS_MANAGE, True),
        (Role.ADMIN, Permission.AUDIT_READ, True),
        (Role.ADMIN, Permission.MEMBERS_INVITE, True),
        (Role.ADMIN, Permission.MEMBERS_MANAGE, False),
        (Role.ADMIN, Permission.BILLING_MANAGE, False),
        (Role.ADMIN, Permission.WORKSPACE_DELETE, False),
        (Role.OWNER, Permission.BILLING_MANAGE, True),
        (Role.OWNER, Permission.OWNERSHIP_TRANSFER, True),
        (Role.OWNER, Permission.WORKSPACE_DELETE, True),
    ],
)
def test_the_matrix(role: Role, permission: Permission, allowed: bool) -> None:
    assert has_permission(role, permission) is allowed


def test_permissions_of_is_sorted_strings() -> None:
    listed = permissions_of(Role.AGENT)
    assert listed == sorted(listed)
    assert "inbox.reply" in listed
    assert "billing.manage" not in listed


def test_only_owners_invite_admins() -> None:
    assert may_invite(Role.OWNER, Role.ADMIN)
    assert may_invite(Role.OWNER, Role.AGENT)
    assert may_invite(Role.ADMIN, Role.AGENT)
    assert not may_invite(Role.ADMIN, Role.ADMIN)
    assert not may_invite(Role.AGENT, Role.AGENT)
    assert Role.OWNER not in INVITABLE_ROLES[Role.OWNER]  # ownership moves by transfer


def test_seat_plan_values_are_free_1_pro_3_max_10() -> None:
    assert [entitlement(p, "members") for p in ("free", "pro", "max")] == [1, 3, 10]


@pytest.mark.parametrize(
    ("members", "pending", "limit", "fits"),
    [
        (1, 0, 1, False),  # Free: the owner fills the only seat
        (1, 0, 3, True),
        (1, 1, 3, True),
        (2, 1, 3, False),  # a pending invitation holds a seat
        (3, 0, 3, False),
        (50, 50, None, True),
    ],
)
def test_seat_counting(members: int, pending: int, limit: int | None, fits: bool) -> None:
    assert seat_check(members=members, pending=pending, limit=limit) is fits


def _invitation(status: str, expires: datetime) -> Any:
    return SimpleNamespace(status=status, expires_at=expires)


def test_invitation_states() -> None:
    assert effective_status(_invitation("pending", NOW + timedelta(days=1)), NOW) == "pending"
    assert effective_status(_invitation("pending", NOW), NOW) == "expired"
    assert effective_status(_invitation("pending", NOW - timedelta(days=1)), NOW) == "expired"
    assert effective_status(_invitation("accepted", NOW - timedelta(days=1)), NOW) == "accepted"
    assert effective_status(_invitation("revoked", NOW + timedelta(days=1)), NOW) == "revoked"


def test_audit_detail_drops_bodies_and_secrets_and_cuts_long_values() -> None:
    detail = clean_detail(
        {
            "conversation_id": "c1",
            "text": "hello customer",
            "body": "hello",
            "signing_secret": "whsec",
            "api_key": "k",
            "note": "x" * 500,
            "count": 3,
        }
    )
    assert detail == {"conversation_id": "c1", "note": "x" * 200, "count": 3}


def test_audit_detail_keeps_at_most_twelve_keys() -> None:
    assert len(clean_detail({f"k{i}": i for i in range(30)})) == 12


async def test_the_fake_sender_records_and_can_fail() -> None:
    sender = FakeInvitationSender()
    first = await sender.invite("a@example.com", redirect_url=None, workspace_id="w")
    second = await sender.invite("b@example.com", redirect_url=None, workspace_id="w")
    assert first != second
    assert [m["email"] for m in sender.sent] == ["a@example.com", "b@example.com"]
    await sender.revoke(first)
    assert sender.revoked == [first]
    sender.fail_next()
    with pytest.raises(InvitationError):
        await sender.invite("c@example.com", redirect_url=None, workspace_id="w")
    await sender.invite("c@example.com", redirect_url=None, workspace_id="w")  # only the next
