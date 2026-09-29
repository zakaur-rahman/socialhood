"""SQLAlchemy models, one module per domain. Importing this package registers them all."""

from socialhood.models import (
    agent,
    ai,
    analytics,
    automations,
    billing,
    connections,
    identity,
    inbox,
    media,
    notifications,
    platform,
    publishing,
)

__all__ = [
    "agent",
    "ai",
    "analytics",
    "automations",
    "billing",
    "connections",
    "identity",
    "inbox",
    "media",
    "notifications",
    "platform",
    "publishing",
]
