"""Notification emails (FR-NOT-02, F-15; T8.5): one template per emailed notification type.

The notification's own title and body are the email's subject and message: producers already
write them plain and specific ("Reconnect @maple.bakery", "@maple.bakery needs reconnecting to
keep receiving messages."), so the in-app panel and the email say the same thing. Each template
adds what the email needs on its own: one line of context, a button that says what it does, and
why the email came. The data (email_deliveries.data) is what services/notifications stored:
``title``, ``body``, ``link`` (workspace-relative, e.g. "/settings/connections"),
``workspace_name`` and ``workspace_slug``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from html import escape
from typing import Any

from socialhood.models.notifications import EmailTemplate
from socialhood.notify.templates.layout import Button, button, link, page, paragraph, text_page
from socialhood.notify.templates.types import RenderedEmail


@dataclass(frozen=True)
class _Kind:
    context: str  # one line after the notification's body
    action: str  # the button
    default_link: str  # when the notification has none
    why: str  # the footer: why this email came


_ALWAYS_ON = "These emails can't be turned off while you're an owner or admin."

KINDS: dict[str, _Kind] = {
    EmailTemplate.ACCOUNT_NEEDS_RECONNECT: _Kind(
        context="Until it's reconnected, new messages and comments from this account don't reach "
        "Social Hood and replies can't be sent from it.",
        action="Reconnect the account",
        default_link="/settings/connections",
        why="You're getting this because an account in {workspace} needs attention. " + _ALWAYS_ON,
    ),
    EmailTemplate.PAYMENT_PROBLEM: _Kind(
        context="Update your payment details to keep your plan. Nothing is deleted if it "
        "moves to Free.",
        action="Open billing",
        default_link="/settings/billing",
        why="You're getting this because you manage billing for {workspace}. " + _ALWAYS_ON,
    ),
    EmailTemplate.PLAN_ACTIVATED: _Kind(
        context="Everything in your plan is ready to use now.",
        action="Open billing",
        default_link="/settings/billing",
        why="You're getting this because you manage billing for {workspace}. " + _ALWAYS_ON,
    ),
    EmailTemplate.PLAN_DOWNGRADED: _Kind(
        context="Nothing was deleted. Upgrade again at any time to turn these back on.",
        action="See your plan",
        default_link="/settings/billing",
        why="You're getting this because you manage billing for {workspace}. " + _ALWAYS_ON,
    ),
    EmailTemplate.POST_FAILED: _Kind(
        context="Open the post to see what went wrong, then edit and retry.",
        action="Open the post",
        default_link="/schedule",
        why="You're getting this because a scheduled post in {workspace} didn't publish. "
        + _ALWAYS_ON,
    ),
}


def app_url(web_base_url: str, slug: str, path: str | None) -> str:
    """An absolute link into the workspace: WEB_BASE_URL/w/{slug}{path}."""
    path = path or "/home"
    if not path.startswith("/"):
        path = "/" + path
    return f"{web_base_url.rstrip('/')}/w/{slug}{path}"


def render(template: str, data: Mapping[str, Any], *, web_base_url: str) -> RenderedEmail:
    kind = KINDS[template]
    title = str(data.get("title") or "").strip() or "Social Hood"
    body = str(data.get("body") or "").strip()
    workspace = str(data.get("workspace_name") or "your workspace")
    slug = str(data.get("workspace_slug") or "")
    target = app_url(web_base_url, slug, data.get("link") or kind.default_link)
    settings_url = app_url(web_base_url, slug, "/settings/notifications")
    why = kind.why.format(workspace=workspace)

    html_body = (
        (paragraph(body) if body else "")
        + paragraph(kind.context)
        + button(Button(kind.action, target))
    )
    footer = (
        f"{escape(why)}<br>"
        + link("Notification settings", settings_url)
        + f" · {escape(workspace)}"
    )
    html = page(
        title=title,
        preheader=body or kind.context,
        heading=title,
        body_html=html_body,
        footer_html=footer,
    )
    lines = [line for line in (body, kind.context) if line]
    text = text_page(
        heading=title,
        lines=[*lines, "", f"{kind.action}: {target}"],
        footer=[why, f"Notification settings: {settings_url}"],
    )
    return RenderedEmail(subject=title, html=html, text=text)
