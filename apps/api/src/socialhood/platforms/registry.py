"""Pick the adapter for an account."""

from __future__ import annotations

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import PlatformAdapter
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.instagram.adapter import InstagramAdapter
from socialhood.platforms.sandbox.adapter import SandboxAdapter, is_sandbox
from socialhood.platforms.whatsapp.adapter import WhatsAppAdapter


def adapter_for(acct: SocialAccount, deps: PlatformDeps) -> PlatformAdapter:
    if is_sandbox(acct):
        if not deps.settings.sandbox_platform_enabled:
            raise PlatformError("platform_rejected", message="The sandbox platform is disabled")
        return SandboxAdapter(deps)
    if acct.platform == "instagram":
        return InstagramAdapter(deps)
    if acct.platform == "whatsapp":
        return WhatsAppAdapter(deps)
    raise PlatformError("platform_rejected", message=f"{acct.platform} is not supported yet")
