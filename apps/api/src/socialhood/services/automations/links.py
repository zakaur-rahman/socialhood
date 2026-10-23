"""Tracked links (GR-15): link buttons in an automation's messages go through ``/l/<code>``.

- **Making them.** When a message with link buttons is queued for a run, each https button
  becomes a ``TrackedLink`` (run, step, button, contact, the original address) and the button is
  sent with ``{base}/l/{code}``. The code is an opaque random token (96 bits), so nothing about
  the run, step or contact is in the URL, and a link can't be guessed. One link per run, step and
  button: a retried send reuses it. The base is ``LINK_BASE_URL``, else ``API_BASE_URL`` (the API
  serves the redirect, webhooks/links.py); with neither, or with the automation's
  ``track_links`` off, buttons are sent as written. The profile button is never tracked.
- **Following them.** The route answers 302 to the stored address, which must be http or https
  (``safe_target``). A click is counted unless ``is_bot`` says the request is a preview or crawler
  (those still get the redirect, so a preview shows the real page), or the same link was already
  counted a few seconds ago (a double tap or a prefetch).
- **What is a bot.** A HEAD request; no User-Agent; the known link-preview and crawler agents
  (Meta's ``facebookexternalhit`` and ``meta-external*`` fetchers, which Instagram and WhatsApp
  use for previews, ``WhatsApp/``, Slack, Telegram, Discord, X, LinkedIn, the search engines, and
  command-line clients); and anything that calls itself a bot, crawler, spider or preview. The
  in-app browsers of Instagram and Facebook are people, even though their agent says so.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import replace
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.automations import Automation, LinkClick, TrackedLink
from socialhood.platforms.base import OutboundButton
from socialhood.services.automations import actions, validation
from socialhood.settings import Settings

CODE_BYTES = 12  # token_urlsafe(12) is 16 characters
DOUBLE_CLICK = timedelta(seconds=5)  # a second click on one link this soon isn't counted
PATH = "/l/"

BOT_AGENTS = (
    "facebookexternalhit",
    "facebot",
    "meta-externalagent",
    "meta-externalfetcher",
    "whatsapp/",
    "twitterbot",
    "slackbot",
    "slack-imgproxy",
    "telegrambot",
    "discordbot",
    "linkedinbot",
    "pinterestbot",
    "googlebot",
    "google-inspectiontool",
    "adsbot-google",
    "bingbot",
    "bingpreview",
    "applebot",
    "duckduckbot",
    "yandex",
    "baiduspider",
    "petalbot",
    "semrushbot",
    "ahrefsbot",
    "mj12bot",
    "curl/",
    "wget/",
    "python-requests",
    "python-httpx",
    "go-http-client",
    "headlesschrome",
)
BOT_WORDS = ("bot", "crawl", "spider", "preview", "scanner")
PEOPLE_IN_APPS = ("instagram", "fban", "fbav")  # in-app browsers: a person is tapping


def new_code() -> str:
    return secrets.token_urlsafe(CODE_BYTES)


def base_url(settings: Settings) -> str | None:
    found = settings.link_base_url or settings.api_base_url
    return found.rstrip("/") if found else None


def is_bot(user_agent: str | None, method: str = "GET") -> bool:
    """Whether a request is a link preview, a crawler or a script rather than a person."""
    if method.upper() == "HEAD":
        return True
    agent = (user_agent or "").strip().lower()
    if not agent:
        return True
    if any(token in agent for token in BOT_AGENTS):
        return True
    if any(token in agent for token in PEOPLE_IN_APPS):
        return False
    return any(word in agent for word in BOT_WORDS)


def safe_target(url: str) -> str | None:
    """The address to redirect to, or None when it isn't a plain http or https link."""
    if not url or any(c.isspace() or ord(c) < 32 for c in url):
        return None
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not host:
        return None
    return url


def _trackable(button: OutboundButton) -> bool:
    profile = actions.PROFILE_URL.split("{")[0]
    return validation.is_https_url(button.url) and not button.url.startswith(profile)


async def track_buttons(
    session: AsyncSession,
    settings: Settings,
    automation: Automation,
    *,
    run_id: uuid.UUID,
    contact_id: uuid.UUID,
    step_id: str,
    buttons: tuple[OutboundButton, ...],
) -> tuple[OutboundButton, ...]:
    """The buttons with their links swapped for tracked ones (the run's lock is held by the
    caller, or the unique key makes a repeat find the first)."""
    base = base_url(settings)
    if base is None or not automation.track_links or not buttons:
        return buttons
    existing = {
        (link.button_index): link
        for link in await session.scalars(
            select(TrackedLink).where(TrackedLink.run_id == run_id, TrackedLink.step_id == step_id)
        )
    }
    out: list[OutboundButton] = []
    for index, button in enumerate(buttons):
        if not _trackable(button):
            out.append(button)
            continue
        link = existing.get(index)
        if link is None or link.url != button.url:
            if link is not None:  # the address changed under the same run: a new code
                await session.delete(link)
                await session.flush()
            link = TrackedLink(
                automation_id=automation.id,
                run_id=run_id,
                contact_id=contact_id,
                step_id=step_id,
                button_index=index,
                code=new_code(),
                title=button.title,
                url=button.url,
            )
            session.add(link)
            await session.flush()
        out.append(replace(button, url=f"{base}{PATH}{link.code}"))
    return tuple(out)


async def count_click(session: AsyncSession, link: TrackedLink, *, now: datetime) -> bool:
    """Record a click on ``link`` (a person's, already told from a bot); False when it repeats
    one counted just before. The caller commits, with the workspace in scope."""
    recent = await session.scalar(
        select(LinkClick.id)
        .where(LinkClick.link_id == link.id, LinkClick.created_at >= now - DOUBLE_CLICK)
        .limit(1)
    )
    if recent is not None:
        return False
    session.add(
        LinkClick(
            link_id=link.id,
            automation_id=link.automation_id,
            run_id=link.run_id,
            contact_id=link.contact_id,
            step_id=link.step_id,
            created_at=now,
        )
    )
    await session.flush()
    return True
