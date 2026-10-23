"""The weekly digest email (FR-NOT-04, T8.7).

Data (email_deliveries.data, written by notify/digest.py): ``workspace_name``,
``workspace_slug`` and ``stats``, the week's numbers as services/overview_stats.py computed them
(``OverviewStats.to_json``) with the weekly report's ``trends`` and ``account`` lists
(services/reports.py ``digest_extras``, GR-34), plus ``unsubscribe_url`` added at send time (a
signed token, never stored). A number the week has no basis for (no conversations, no replies, an
insight with no readings) reads "No data" rather than 0%. The email links to the report page for
the same week.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from html import escape
from typing import Any

from socialhood.notify.templates.layout import (
    Button,
    Row,
    button,
    data_table,
    link,
    page,
    paragraph,
    text_page,
)
from socialhood.notify.templates.notifications import app_url
from socialhood.notify.templates.types import RenderedEmail

INTENT_LABELS = {
    "pricing": "Prices",
    "product_inquiry": "Product questions",
    "purchase": "Ready to buy",
    "order_status": "Order status",
    "shipping": "Shipping",
    "support": "Support",
    "complaint": "Complaints",
    "refund": "Refunds",
    "feedback": "Feedback",
    "collaboration": "Collaborations",
    "greeting": "Greetings",
    "spam": "Spam",
    "other": "Other",
}
NO_DATA = "No data"
DASH = chr(0x2013)  # en dash
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def period_label(since: date, until: date) -> str:
    """ "22-28 Sep", "29 Sep - 5 Oct", "29 Dec 2025 - 4 Jan 2026", with en dashes."""
    if since.year != until.year:
        return (
            f"{since.day} {MONTHS[since.month - 1]} {since.year} {DASH} "
            f"{until.day} {MONTHS[until.month - 1]} {until.year}"
        )
    if since.month != until.month:
        return f"{since.day} {MONTHS[since.month - 1]} {DASH} {until.day} {MONTHS[until.month - 1]}"
    return f"{since.day}{DASH}{until.day} {MONTHS[until.month - 1]}"


def duration(seconds: int | None) -> str:
    """45 s, 12 min, 3 h 20 min, 2 d 4 h."""
    if seconds is None:
        return NO_DATA
    if seconds < 60:
        return f"{seconds} s"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} h {minutes} min" if minutes else f"{hours} h"
    days, hours = divmod(hours, 24)
    return f"{days} d {hours} h" if hours else f"{days} d"


def percent(value: float | None) -> str:
    return NO_DATA if value is None else f"{round(value)}%"


def plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n:,} {one if n == 1 else (many or one + 's')}"


def clip(text: str | None, limit: int = 60) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _rows(stats: Mapping[str, Any]) -> list[Row]:
    conversations = int(stats.get("conversations") or 0)
    replied = int(stats.get("conversations_replied") or 0)
    by_ai = int(stats.get("handled_by_ai") or 0)
    responses = int(stats.get("first_responses") or 0)
    return [
        Row("Messages received", f"{int(stats.get('messages_received') or 0):,}"),
        Row(
            "Reply rate",
            percent(stats.get("reply_rate")),
            f"Replied in {replied:,} of {plural(conversations, 'conversation')}"
            if conversations
            else None,
        ),
        Row(
            "Median first response",
            duration(stats.get("median_first_response_s")),
            f"Across {plural(responses, 'first reply', 'first replies')}" if responses else None,
        ),
        Row(
            "Handled by AI",
            percent(stats.get("handled_by_ai_rate")),
            f"{by_ai:,} of {plural(replied, 'replied conversation')}" if replied else None,
        ),
        Row("Still marked “Needs you”", plural(int(stats.get("needs_you") or 0), "conversation")),
    ]


def _count(value: float | None, unit: str) -> str:
    if value is None:
        return NO_DATA
    if unit == "percent":
        return percent(value)
    if unit == "seconds":
        return duration(round(value))
    return f"{round(value):,}"


def _change(item: Mapping[str, Any]) -> str | None:
    """ "Up 12.5% on the week before (was 80)": the change as the service worked it out."""
    direction = item.get("direction")
    previous = item.get("previous")
    if previous is None:
        return "No data for the week before"
    was = _count(previous, str(item.get("unit") or "count"))
    if direction == "flat":
        return f"About the same as the week before (was {was})"
    if direction not in ("up", "down"):
        return None
    word = "Up" if direction == "up" else "Down"
    if item.get("change_points") is not None:
        return f"{word} {abs(float(item['change_points'])):g} points on the week before (was {was})"
    if item.get("change_pct") is not None:
        return f"{word} {abs(float(item['change_pct'])):g}% on the week before (was {was})"
    return f"{word} from {was} the week before"


def _trends(stats: Mapping[str, Any]) -> list[Row]:
    return [
        Row(
            str(item["label"]),
            _count(item.get("value"), str(item.get("unit") or "count")),
            _change(item),
        )
        for item in stats.get("trends") or []
    ]


GAPS = {
    "insights_not_granted": "Instagram insights aren't allowed for this account",
    "no_readings": "No readings for this week yet",
    "no_account": "No Instagram account connected",
}


def _account(stats: Mapping[str, Any]) -> list[Row]:
    rows: list[Row] = []
    for item in stats.get("account") or []:
        known, total = int(item.get("days_known") or 0), int(item.get("days_total") or 0)
        value = item.get("value")
        notes = [GAPS.get(str(item.get("unavailable")), "") if value is None else ""]
        if value is not None and known < total:
            notes.append(f"Counts {known} of {total} days")
        if value is not None:
            notes.append(_change({**item, "unit": "count"}) or "")
        rows.append(
            Row(
                str(item["label"]), _count(value, "count"), "; ".join(n for n in notes if n) or None
            )
        )
    return rows


def _intents(stats: Mapping[str, Any]) -> list[Row]:
    return [
        Row(
            INTENT_LABELS.get(str(item["intent"]), str(item["intent"]).capitalize()),
            plural(int(item["count"]), "message"),
        )
        for item in stats.get("top_intents") or []
    ]


def _questions(stats: Mapping[str, Any]) -> list[Row]:
    return [
        Row(clip(str(item["topic"]), 80), f"Asked {plural(int(item['asked']), 'time')}")
        for item in stats.get("top_questions") or []
    ]


def _post(stats: Mapping[str, Any]) -> Mapping[str, Any] | None:
    posts: Sequence[Mapping[str, Any]] = stats.get("top_posts") or []
    return posts[0] if posts else None


def render(data: Mapping[str, Any], *, web_base_url: str) -> RenderedEmail:
    stats: Mapping[str, Any] = data.get("stats") or {}
    workspace = str(data.get("workspace_name") or "your workspace")
    slug = str(data.get("workspace_slug") or "")
    since, until = date.fromisoformat(stats["since"]), date.fromisoformat(stats["until"])
    period = period_label(since, until)
    subject = f"Your week at {workspace}: {period}"
    received = int(stats.get("messages_received") or 0)
    intro = (
        f"Here's how {period} went: {plural(received, 'message')} received."
        if received
        else f"No messages came in {period}."
    )
    home = app_url(web_base_url, slug, "/home")
    inbox = app_url(web_base_url, slug, "/inbox")
    knowledge = app_url(web_base_url, slug, "/knowledge")
    settings_url = app_url(web_base_url, slug, "/settings/notifications")
    unsubscribe = str(data.get("unsubscribe_url") or settings_url)

    report = app_url(web_base_url, slug, f"/reports?week={since.isoformat()}")
    rows, intents, questions, post = _rows(stats), _intents(stats), _questions(stats), _post(stats)
    trends, account = _trends(stats), _account(stats)
    html_parts = [paragraph(intro), data_table("Messages", rows)]
    text_lines = [intro, ""]
    text_lines += [
        f"{row.label}: {row.value}" + (f" ({row.note})" if row.note else "") for row in rows
    ]
    if trends:
        html_parts.append(data_table("Against the week before", trends))
        text_lines += ["", "Against the week before:"]
        text_lines += [
            f"- {row.label}: {row.value}" + (f" ({row.note})" if row.note else "") for row in trends
        ]
    if account:
        html_parts.append(data_table("Your Instagram account", account))
        text_lines += ["", "Your Instagram account:"]
        text_lines += [
            f"- {row.label}: {row.value}" + (f" ({row.note})" if row.note else "")
            for row in account
        ]
    if intents:
        html_parts.append(data_table("What customers wrote about", intents))
        text_lines += ["", "What customers wrote about:"]
        text_lines += [f"- {row.label}: {row.value}" for row in intents]
    if questions:
        html_parts.append(data_table("Questions the AI couldn't answer", questions))
        html_parts.append(
            paragraph("Add the answers to your knowledge so the AI can reply next time.")
        )
        text_lines += ["", "Questions the AI couldn't answer:"]
        text_lines += [f"- {row.label}: {row.value}" for row in questions]
        text_lines.append(f"Add the answers: {knowledge}")
    if post is not None:
        caption = clip(post.get("caption"), 70) or "Untitled post"
        post_url = app_url(web_base_url, slug, f"/comments/{post['post_id']}")
        html_parts.append(
            data_table(
                "Post with the most comments",
                [Row(caption, plural(int(post["comments"]), "comment"), None)],
            )
        )
        text_lines += [
            "",
            f"Post with the most comments: {caption}, "
            f"{plural(int(post['comments']), 'comment')} ({post_url})",
        ]
    html_parts.append(button(Button("See the full report", report)))
    text_lines += [
        "",
        f"See the full report, with the last 8 weeks: {report}",
        f"Open Social Hood: {home}",
        f"Inbox: {inbox}",
    ]

    footer_html = (
        f"You're getting the weekly digest of {escape(workspace)}. "
        + link("Unsubscribe", unsubscribe)
        + " · "
        + link("Notification settings", settings_url)
    )
    html = page(
        title=subject,
        preheader=intro,
        heading=f"Your week at {workspace}",
        body_html="".join(html_parts),
        footer_html=footer_html,
    )
    text = text_page(
        heading=f"Your week at {workspace} ({period})",
        lines=text_lines,
        footer=[
            f"You're getting the weekly digest of {workspace}.",
            f"Unsubscribe: {unsubscribe}",
            f"Notification settings: {settings_url}",
        ],
    )
    return RenderedEmail(subject=subject, html=html, text=text)
