"""Flow analytics (GR-15): one automation's per-step funnel and its A/B split results."""

from __future__ import annotations

from typing import Literal

from socialhood.schemas.common import ResponseModel


class FunnelStep(ResponseModel):
    """What happened at one step over the period, from the runs that reached it.

    ``delivered`` and ``read`` are what the platform reported for the step's message (a read
    receipt only where the platform sends one); ``taps`` are quick replies tapped at a message;
    ``link_clicks`` are counted clicks on its tracked link buttons, ``link_clickers`` the people;
    ``captures`` are answers a question saved, ``skipped`` the ones that never fitted, and
    ``consents`` the marketing "yes" answers.
    """

    step_id: str
    kind: str  # send, ask, branch, action, delay, randomize, ai_reply or end
    title: str
    text: str | None = None
    # What the step offers, so a screen shows a count only where one can happen.
    link_buttons: int = 0
    quick_replies: int = 0
    reached: int
    sent: int
    delivered: int
    read: int
    failed: int
    taps: int
    link_clicks: int
    link_clickers: int
    captures: int
    skipped: int
    consents: int


class SplitBranch(ResponseModel):
    """One path of a Split step: the runs that took it, and what happened on the steps after it."""

    path: int
    label: str  # "Path A"
    weight: int
    runs: int
    delivered: int
    read: int
    taps: int
    link_clicks: int
    captures: int


class SplitResult(ResponseModel):
    step_id: str
    branches: list[SplitBranch]


class AutomationFunnel(ResponseModel):
    days: Literal[7, 30, 90]
    runs: int
    links_tracked: bool  # false: link buttons go out as written, so clicks can't be counted
    steps: list[FunnelStep]
    splits: list[SplitResult]
