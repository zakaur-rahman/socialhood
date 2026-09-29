"""SQLAlchemy models, one module per domain. Importing this package registers them all."""

from socialhood.models import (
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
)

__all__ = [
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
]
