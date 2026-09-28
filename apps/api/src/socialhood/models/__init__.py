"""SQLAlchemy models, one module per domain. Importing this package registers them all."""

from socialhood.models import ai, billing, connections, identity, notifications, platform

__all__ = ["ai", "billing", "connections", "identity", "notifications", "platform"]
