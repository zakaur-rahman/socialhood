"""Clerk invitations (GR-19): the email with the sign-up link is Clerk's, and so is its secret.

``InvitationSender`` is the interface; ``ClerkInvitationSender`` calls the Backend API and
``FakeInvitationSender`` keeps everything in memory for tests and for running without Clerk
(``CLERK_INVITATIONS_PROVIDER=fake``, refused in production). ``get_invitation_sender`` picks one
from the settings; tests swap it with ``use_invitation_sender``, so no test reaches Clerk.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from socialhood.auth.clerk import CLERK_API
from socialhood.settings import Settings


class InvitationError(Exception):
    """Clerk could not send or revoke the invitation (down, refused, or not configured)."""


class InvitationSender(Protocol):
    async def invite(self, email: str, *, redirect_url: str | None, workspace_id: str) -> str:
        """Send the invitation email; return Clerk's invitation id."""
        ...

    async def revoke(self, invitation_id: str) -> None: ...


class ClerkInvitationSender:
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self.http = http
        self.secret = (
            settings.clerk_secret_key.get_secret_value() if settings.clerk_secret_key else ""
        )

    async def _post(self, path: str, body: dict[str, Any] | None = None) -> httpx.Response:
        if not self.secret:
            raise InvitationError("CLERK_SECRET_KEY is not set")
        try:
            return await self.http.post(
                f"{CLERK_API}{path}",
                json=body or {},
                headers={"Authorization": f"Bearer {self.secret}"},
            )
        except httpx.HTTPError as error:
            raise InvitationError("clerk_unreachable") from error

    async def invite(self, email: str, *, redirect_url: str | None, workspace_id: str) -> str:
        body: dict[str, Any] = {
            "email_address": email,
            "notify": True,
            "ignore_existing": True,
            "public_metadata": {"workspace_id": workspace_id},
        }
        if redirect_url:
            body["redirect_url"] = redirect_url
        response = await self._post("/invitations", body)
        if response.status_code not in (200, 201):
            raise InvitationError(f"clerk_status_{response.status_code}")
        return str(response.json()["id"])

    async def revoke(self, invitation_id: str) -> None:
        response = await self._post(f"/invitations/{invitation_id}/revoke")
        # 404: already used or gone, which is what the caller wanted.
        if response.status_code not in (200, 404):
            raise InvitationError(f"clerk_status_{response.status_code}")


@dataclass
class FakeInvitationSender:
    """Records what would have been sent. ``fail_next`` makes the next call raise."""

    sent: list[dict[str, Any]] = field(default_factory=list)
    revoked: list[str] = field(default_factory=list)
    failing: bool = False
    _ids: Iterator[int] = field(default_factory=lambda: itertools.count(1))

    def fail_next(self) -> None:
        self.failing = True

    def _check(self) -> None:
        if self.failing:
            self.failing = False
            raise InvitationError("fake_failure")

    async def invite(self, email: str, *, redirect_url: str | None, workspace_id: str) -> str:
        self._check()
        invitation_id = f"inv_fake_{next(self._ids)}"
        self.sent.append(
            {
                "id": invitation_id,
                "email": email,
                "redirect_url": redirect_url,
                "workspace_id": workspace_id,
            }
        )
        return invitation_id

    async def revoke(self, invitation_id: str) -> None:
        self._check()
        self.revoked.append(invitation_id)


_override: list[InvitationSender] = []
_process_fake = FakeInvitationSender()


def get_invitation_sender(http: httpx.AsyncClient, settings: Settings) -> InvitationSender:
    if _override:
        return _override[-1]
    if settings.clerk_invitations_provider == "fake":
        return _process_fake
    return ClerkInvitationSender(http, settings)


@contextmanager
def use_invitation_sender(sender: InvitationSender) -> Iterator[InvitationSender]:
    """Tests: every get_invitation_sender() in the block returns ``sender``."""
    _override.append(sender)
    try:
        yield sender
    finally:
        _override.pop()
