"""Product API, all under /v1 (TR-API-01).

Each router carries the full /v1 prefix itself and is included on the app without a prefix:
FastAPI reports route templates without include-time prefixes, and logs and metrics need the
full template.
"""

from fastapi import APIRouter

from socialhood.api.v1 import (
    accounts,
    conversations,
    events,
    me,
    media,
    messages,
    notifications,
    oauth,
    privacy,
    scheduled,
    whatsapp,
    workspaces,
)

ROUTERS: tuple[APIRouter, ...] = (
    me.router,
    workspaces.router,
    accounts.router,
    notifications.router,
    oauth.router,
    privacy.router,
    conversations.router,
    messages.router,
    media.router,
    scheduled.router,
    events.router,
    whatsapp.router,
)
