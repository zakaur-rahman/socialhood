"""Email templates (T8.5, T8.7): one per models/notifications.EmailTemplate, each rendering a
subject, an HTML body and a plain-text body from an email_deliveries row's ``data``. Plain,
specific copy (UX-COPY-01); every link is absolute on WEB_BASE_URL; the digest's footer carries
the one-click unsubscribe link.

- notifications.py: account_needs_reconnect, payment_problem, plan_activated, plan_downgraded and
  post_failed, from the notification's title, body and link.
- digest.py: weekly_digest, from the week's numbers (services/overview_stats.py).
- layout.py: the shared, accessible layout and the plain-text twin.

Rendering is deterministic (the same row renders the same email), so a retried send carries the
same content under the same Idempotency-Key.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from socialhood.models.notifications import EmailTemplate
from socialhood.notify.templates import digest, notifications
from socialhood.notify.templates.types import RenderedEmail

__all__ = ["RenderedEmail", "render"]


def render(template: str, data: Mapping[str, Any], *, web_base_url: str) -> RenderedEmail:
    """``ValueError`` for a template that doesn't exist."""
    if template == EmailTemplate.WEEKLY_DIGEST:
        return digest.render(data, web_base_url=web_base_url)
    if template in notifications.KINDS:
        return notifications.render(template, data, web_base_url=web_base_url)
    raise ValueError(f"unknown email template {template!r}")
