"""The shared email layout: one light, single-column page that reads well in any client, with a
plain-text twin.

Accessibility: ``lang`` and a ``<title>``, one ``<h1>``, layout tables marked
``role="presentation"``, data tables with row headers, text at least 15 px, body text #27272a and
secondary text #52525b on white (both above 7:1), a button whose label says what it does, and no
images, so nothing depends on images loading. Every value is HTML-escaped here; templates pass
plain strings.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from html import escape

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
INK = "#09090b"
BODY = "#27272a"
MUTED = "#52525b"
LINE = "#e4e4e7"
PAGE = "#f4f4f5"


@dataclass(frozen=True)
class Button:
    label: str
    url: str


@dataclass(frozen=True)
class Row:
    """One line of a data table: a label, its value and, optionally, a note under the value."""

    label: str
    value: str
    note: str | None = None


def paragraph(text: str) -> str:
    return f'<p style="margin:0 0 14px;font:400 15px/1.6 {FONT};color:{BODY};">{escape(text)}</p>'


def link(label: str, url: str) -> str:
    style = f"color:{INK};text-decoration:underline;"
    return f'<a href="{escape(url)}" style="{style}">{escape(label)}</a>'


def button(action: Button) -> str:
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:6px 0 0;">'
        f'<tr><td style="border-radius:8px;background:{INK};">'
        f'<a href="{escape(action.url)}" style="display:inline-block;padding:12px 20px;'
        f'font:600 15px/1.2 {FONT};color:#ffffff;text-decoration:none;border-radius:8px;">'
        f"{escape(action.label)}</a></td></tr></table>"
    )


def data_table(caption: str, rows: Sequence[Row]) -> str:
    cells = []
    for row in rows:
        note = (
            f'<div style="font:400 13px/1.5 {FONT};color:{MUTED};">{escape(row.note)}</div>'
            if row.note
            else ""
        )
        cells.append(
            f'<tr><th scope="row" style="padding:10px 12px 10px 0;border-top:1px solid {LINE};'
            f"text-align:left;vertical-align:top;font:400 15px/1.5 {FONT};color:{MUTED};"
            f'width:48%;">{escape(row.label)}</th>'
            f'<td style="padding:10px 0;border-top:1px solid {LINE};vertical-align:top;'
            f'font:600 15px/1.5 {FONT};color:{INK};">{escape(row.value)}{note}</td></tr>'
        )
    return (
        '<table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;'
        'margin:4px 0 18px;">'
        f'<caption style="text-align:left;padding:0 0 6px;font:600 13px/1.4 {FONT};'
        f'color:{MUTED};text-transform:uppercase;letter-spacing:0.04em;">{escape(caption)}</caption>'
        + "".join(cells)
        + "</table>"
    )


def page(*, title: str, preheader: str, heading: str, body_html: str, footer_html: str) -> str:
    """The whole HTML document. ``body_html`` and ``footer_html`` are already escaped."""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="color-scheme" content="light"><meta name="supported-color-schemes" '
        f'content="light"><title>{escape(title)}</title></head>'
        f'<body style="margin:0;padding:0;background:{PAGE};">'
        f'<div style="display:none;max-height:0;overflow:hidden;">{escape(preheader)}</div>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:{PAGE};"><tr><td align="center" style="padding:24px 12px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:560px;background:#ffffff;border-radius:12px;">'
        f'<tr><td style="padding:24px 28px 0;font:700 15px/1.4 {FONT};color:{INK};">'
        "Social Hood</td></tr>"
        f'<tr><td style="padding:14px 28px 6px;"><h1 style="margin:0 0 8px;font:600 21px/1.35 '
        f'{FONT};color:{INK};">{escape(heading)}</h1></td></tr>'
        f'<tr><td style="padding:0 28px 26px;">{body_html}</td></tr>'
        "</table>"
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:560px;"><tr>'
        f'<td style="padding:16px 28px 0;font:400 13px/1.6 {FONT};color:{MUTED};">'
        f"{footer_html}</td></tr></table>"
        "</td></tr></table></body></html>"
    )


def text_page(*, heading: str, lines: Sequence[str], footer: Sequence[str]) -> str:
    """The plain-text part: the same content, links written out."""
    parts = ["Social Hood", "", heading, "", *lines, "", "--", *footer]
    return "\n".join(parts).strip() + "\n"
