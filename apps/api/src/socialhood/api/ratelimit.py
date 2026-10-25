"""Route dependencies for the TR-API-07 limits (the windows are in security/ratelimit.py).

``dependencies=[SENDS]`` on a route counts it against its workspace's sends. The workspace
membership is resolved first (the same cached ``workspace_ctx`` the route uses), so a request
for a workspace the caller isn't in is 404 and never spends that workspace's budget.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request

from socialhood.auth.deps import WorkspaceContext, workspace_ctx
from socialhood.security import ratelimit

# Every dependency made here, so a test can check that each route sits behind a limit.
LIMIT_DEPENDENCIES: set[Callable[..., Awaitable[None]]] = set()


def per_workspace(name: str) -> Callable[..., Awaitable[None]]:
    async def dependency(
        request: Request, ctx: Annotated[WorkspaceContext, Depends(workspace_ctx)]
    ) -> None:
        await ratelimit.enforce(request, name, str(ctx.workspace_id))

    LIMIT_DEPENDENCIES.add(dependency)
    return dependency


def per_ip(name: str) -> Callable[..., Awaitable[None]]:
    async def dependency(request: Request) -> None:
        await ratelimit.enforce(request, name, ratelimit.client_ip(request))

    LIMIT_DEPENDENCIES.add(dependency)
    return dependency


# 60 a minute per workspace: anything that sends or schedules to a customer or platform.
SENDS = Depends(per_workspace("sends"))
# 20 a minute per workspace: requests that call the model.
AI = Depends(per_workspace("ai"))
# 30 a minute per IP: public OAuth callbacks.
OAUTH_CALLBACK = Depends(per_ip("oauth_callback"))
# 60 a minute per IP: the other routes without sign-in (webhooks excepted).
PUBLIC = Depends(per_ip("public"))
# GR-28, the website chat widget: its public routes (the other limits are counted per visitor in
# api/v1/widget_public.py).
WIDGET_FRAME = Depends(per_ip("widget_frame"))
WIDGET_SESSION = Depends(per_ip("widget_session"))
WIDGET_SEND = Depends(per_ip("widget_send_ip"))
WIDGET_POLL = Depends(per_ip("widget_poll_ip"))
WIDGET_EMAIL = Depends(per_ip("widget_email_ip"))
