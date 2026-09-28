"""SQLAlchemy models, one module per domain. Importing this package registers them all."""

from socialhood.models import ai, billing, identity, platform

__all__ = ["ai", "billing", "identity", "platform"]
