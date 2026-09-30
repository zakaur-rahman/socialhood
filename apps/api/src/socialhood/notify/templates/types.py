"""What a template renders."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html: str
    text: str
