"""Product API, all under /v1 (TR-API-01).

Each router carries the full /v1 prefix itself and is included on the app without a prefix:
FastAPI reports route templates without include-time prefixes, and logs and metrics need the
full template.
"""

from fastapi import APIRouter

from socialhood.api.v1 import (
    accounts,
    agent,
    ai,
    analytics,
    automations,
    billing,
    captions,
    comments,
    conversations,
    events,
    knowledge,
    me,
    media,
    messages,
    notifications,
    oauth,
    posts,
    privacy,
    publishing,
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
    automations.router,
    posts.router,
    ai.router,
    knowledge.router,
    billing.router,
    comments.router,
    analytics.router,
    publishing.router,
    captions.router,
    agent.router,
)
