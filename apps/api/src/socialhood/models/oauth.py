"""The OAuth records behind AI app connections (C-165 phase C; docs/architecture/mcp/01-design.md
§3.2 A2, §3.6, §10).

- ``oauth_clients``: the AI apps that may ask to connect. Not a workspace's: one row per client
  across Amplychat. A client is either a Client ID Metadata Document (``kind = cimd``, the
  ``client_id`` is the document's https URL, re-read at most once a day) or one registered with
  Dynamic Client Registration (``kind = dcr``, a generated ``client_id``; deleted after 30 days
  unused with no live connection). ``blocked_at`` is the operators' block list (§6.7).
- ``mcp_connections``: one member's consent for one client in one workspace (the "grant"):
  the scopes they allowed, when it was last used, and when and by whom it was revoked. Every
  token belongs to one. Settings, Connected AI apps lists these.
- ``oauth_codes``: an authorization code, single use and short-lived (60 seconds), with the
  PKCE challenge, the redirect URI and the resource it was asked for. Only its SHA-256 is kept.
  ``connection_id`` is set once it is exchanged, so a second use can revoke what the first made.
- ``oauth_tokens``: access tokens (``sho_``, one hour) and refresh tokens (``shr_``, rotated on
  every use). Only SHA-256 hashes are kept, like API keys. ``family_id`` ties one code's chain
  of refresh tokens together; ``used_at`` on a refresh token means it was rotated, and seeing it
  again revokes the connection (reuse detection).

Codes, tokens and connections are tenant rows; finding one by its hash is the one
cross-workspace lookup, in auth/mcp_oauth.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, CreatedAtMixin, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped


def _in(column: str, enum: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(m.value) for m in enum)})"


class ClientKind(StrEnum):
    CIMD = "cimd"
    DCR = "dcr"


class ClientAuth(StrEnum):
    """How a client authenticates at the token and revocation endpoints."""

    NONE = "none"  # a public client (PKCE is its proof)
    SECRET_POST = "client_secret_post"  # noqa: S105  (a method's name)
    SECRET_BASIC = "client_secret_basic"  # noqa: S105


class TokenKind(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class RevokeReason(StrEnum):
    MEMBER = "member"  # someone revoked it in Settings
    CLIENT = "client"  # the client revoked its refresh token (RFC 7009)
    REFRESH_REUSE = "refresh_reuse"  # a rotated refresh token came back
    CODE_REUSE = "code_reuse"  # the code it came from was used twice
    ALL = "all"  # "Disconnect all"


class OAuthClient(IdMixin, TimestampMixin, Base):
    __tablename__ = "oauth_clients"

    client_id: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    client_name: Mapped[str] = mapped_column(Text)
    client_uri: Mapped[str | None] = mapped_column(Text)
    logo_uri: Mapped[str | None] = mapped_column(Text)
    redirect_uris: Mapped[list[str]] = mapped_column(ARRAY(Text))
    token_endpoint_auth_method: Mapped[str] = mapped_column(Text)
    client_secret_hash: Mapped[str | None] = mapped_column(Text)  # SHA-256, DCR only
    software_id: Mapped[str | None] = mapped_column(Text)
    software_version: Mapped[str | None] = mapped_column(Text)
    metadata_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("client_id"),
        CheckConstraint(_in("kind", ClientKind), name="kind"),
        CheckConstraint(_in("token_endpoint_auth_method", ClientAuth), name="auth_method"),
        CheckConstraint("char_length(client_name) BETWEEN 1 AND 100", name="name_length"),
        CheckConstraint("cardinality(redirect_uris) BETWEEN 1 AND 10", name="redirect_uris"),
    )


class McpConnection(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "mcp_connections"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    oauth_client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("oauth_clients.id", ondelete="CASCADE")
    )
    client_name: Mapped[str] = mapped_column(Text)  # as the member saw it on the consent page
    redirect_uri: Mapped[str] = mapped_column(Text)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text))
    resource: Mapped[str] = mapped_column(Text)  # the audience (RFC 8707): our /mcp URL
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # 180 days, absolute
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    revoke_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            f"revoke_reason IS NULL OR {_in('revoke_reason', RevokeReason)}", name="revoke_reason"
        ),
        Index("ix_mcp_connections_user_id", "user_id"),
        Index("ix_mcp_connections_oauth_client_id", "oauth_client_id"),
    )


class OAuthCode(IdMixin, CreatedAtMixin, TenantScoped, Base):
    __tablename__ = "oauth_codes"

    code_hash: Mapped[str] = mapped_column(Text)
    oauth_client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("oauth_clients.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    client_name: Mapped[str] = mapped_column(Text)
    redirect_uri: Mapped[str] = mapped_column(Text)
    code_challenge: Mapped[str] = mapped_column(Text)  # S256 only
    resource: Mapped[str] = mapped_column(Text)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mcp_connections.id", ondelete="SET NULL")
    )

    __table_args__ = (UniqueConstraint("code_hash"),)


class OAuthToken(IdMixin, CreatedAtMixin, TenantScoped, Base):
    __tablename__ = "oauth_tokens"

    token_hash: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mcp_connections.id", ondelete="CASCADE")
    )
    family_id: Mapped[uuid.UUID] = mapped_column()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # refresh: rotated
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("token_hash"),
        CheckConstraint(_in("kind", TokenKind), name="kind"),
        Index("ix_oauth_tokens_connection_id", "connection_id"),
    )
