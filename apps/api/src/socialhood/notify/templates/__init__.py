"""Email templates (T8.5, T8.7): one per models/notifications.EmailTemplate, each rendering a
subject, an HTML body and a plain-text body from an email_deliveries row's ``data``. Plain,
specific copy (UX-COPY-01); every link is absolute on WEB_BASE_URL; the digest's footer carries
the one-click unsubscribe link.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html: str
    text: str


def render(template: str, data: Mapping[str, Any], *, web_base_url: str) -> RenderedEmail:
    raise NotImplementedError("T8.5")
