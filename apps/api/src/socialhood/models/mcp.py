"""The MCP server's records (C-165; docs/architecture/mcp/01-design.md §6.3, §5.3, §10).

- ``mcp_tool_calls``: one row per ``tools/call``, whatever the outcome (the audit, §6.3): who
  (member, credential, client), which tool, the arguments as a digest plus a redacted copy, the
  outcome and how long it took. Never the AI conversation, never customer text (the arguments
  are what the AI sent us; the results aren't stored). Kept 90 days (jobs/tasks/retention).
- ``mcp_uploads``: a media upload ticket (§5). Phase B's ``start_media_upload`` makes them;
  ``get_media_upload`` reads them. A ticket is a handle the model passes back, re-authorised on
  every call (tenancy), never a capability.

The workspace's own switch is ``workspaces.ai_connections_mode`` (models/identity.py).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, CreatedAtMixin, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped


def _in(column: str, enum: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(m.value) for m in enum)})"


class AiConnectionsMode(StrEnum):
    """What AI clients may do in a workspace (§6.7), least first."""

    OFF = "off"
    READ_ONLY = "read_only"
    READ_DRAFTS = "read_drafts"
    FULL = "full"


class CredentialKind(StrEnum):
    API_KEY = "api_key"
    OAUTH = "oauth"  # Phase C


class CallOutcome(StrEnum):
    OK = "ok"
    ERROR = "error"  # the tool ran and refused (a service's ApiError) or failed
    REFUSED = "refused"  # stopped before the tool: mode, scope, role, plan, a limit, the arguments


class McpToolCall(IdMixin, CreatedAtMixin, TenantScoped, Base):
    __tablename__ = "mcp_tool_calls"

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    credential_kind: Mapped[str] = mapped_column(Text)
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("api_keys.id", ondelete="SET NULL")
    )
    # Phase C's OAuth grant (mcp_connections); no foreign key until that table exists.
    connection_id: Mapped[uuid.UUID | None] = mapped_column()
    # "API key “Codex laptop”", kept as it read then, so the row reads right after a revoke.
    credential_label: Mapped[str] = mapped_column(Text)
    client_name: Mapped[str | None] = mapped_column(Text)
    client_version: Mapped[str | None] = mapped_column(Text)
    tool: Mapped[str] = mapped_column(Text)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    arguments_digest: Mapped[str] = mapped_column(Text)  # SHA-256 of the canonical arguments
    outcome: Mapped[str] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int] = mapped_column(Integer)
    request_id: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(_in("credential_kind", CredentialKind), name="credential_kind"),
        CheckConstraint(_in("outcome", CallOutcome), name="outcome"),
        CheckConstraint("char_length(tool) BETWEEN 1 AND 64", name="tool_length"),
        Index("ix_mcp_tool_calls_workspace_id_created_at", "workspace_id", "created_at"),
        Index("ix_mcp_tool_calls_api_key_id", "api_key_id"),
    )


class UploadStatus(StrEnum):
    WAITING = "waiting"
    UPLOADED = "uploaded"
    EXPIRED = "expired"
    REJECTED = "rejected"


class McpUpload(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "mcp_uploads"

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(Text)  # image, video
    status: Mapped[str] = mapped_column(Text, server_default=text("'waiting'"))
    public_id: Mapped[str | None] = mapped_column(Text)
    media_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL")
    )
    reason: Mapped[str | None] = mapped_column(Text)  # why it was rejected, in plain words
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("kind IN ('image', 'video')", name="kind"),
        CheckConstraint(_in("status", UploadStatus), name="status"),
    )
