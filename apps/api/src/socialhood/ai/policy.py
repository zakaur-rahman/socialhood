"""The auto-reply policy (TR-AI-07; FR-SUG-04, FR-SUG-06, F-09). Pure: no database, no clock.

``evaluate`` runs the 13 checks in TR-AI-07's order on facts the caller loaded
(``PolicyInput``). Every check is evaluated and recorded as {n, name, passed, value}, so the
decision popover can show all of them; the first failure decides the outcome:

 #  check                                                     fails as
 1  the effective mode is auto                                skipped · mode_not_auto
 2  the plan allows auto and credits are available            skipped · quota_exhausted
 3  not paused by a human takeover                            skipped · paused
 4  no automation handled the message                         skipped · automation_handled
 5  the reply window is open                                  escalated · window_closed
 6  the analysis does not ask for a human                     escalated · the analysis reason
 7  intent is not refund or complaint; no escalation phrase   escalated · refund, complaint or
                                                                          policy_keyword
 8  sentiment_score > -0.5                                    escalated · negative_sentiment
 9  the suggestion can answer                                 escalated · out_of_knowledge
 10 confidence >= AUTO_MIN_CONFIDENCE                         escalated · low_confidence
 11 fact questions use a source >= AI_RETRIEVAL_MIN_SIM       escalated · out_of_knowledge
 12 no AI reply to this message yet; < 5 in the last hour     skipped · rate_capped
 13 the output filter passes (ai/output_filter)               escalated · output_blocked

No analysis for the message fails check 6 as low_confidence: Auto never sends without the
analysis' human, intent and sentiment signals (a P5 decision).

Small talk (C-062): Auto may answer a greeting, thanks or goodbye. Check 11 asks for a knowledge
source only for FACT_INTENTS, so a small-talk reply (the model's under suggest.v3, or the fixed one
from services/suggestions/small_talk) is sent when it passes the rest like any reply: confidence
at least AUTO_MIN_CONFIDENCE, no escalation signal, the rate cap and the output filter. A "Hi,
what's the price?" is a pricing question and still needs knowledge. Escalation phrases are the
built-in ones below plus the workspace's own (FR-SUG-06), matched as whole words or phrases in
the message answered, ignoring case.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from socialhood.ai import output_filter
from socialhood.services.automations.matching import keyword_matches, normalize

Outcome = Literal["auto_sent", "escalated", "skipped"]

FACT_INTENTS = frozenset({"pricing", "product_inquiry", "purchase", "order_status", "shipping"})
ESCALATING_INTENTS = frozenset({"refund", "complaint"})
NEGATIVE_SENTIMENT = -0.5
MAX_AI_REPLIES_PER_HOUR = 5

# FR-SUG-06 built-in escalation phrases: refunds, legal threats and asking for a person. Checked
# with the workspace's own phrases in check 7 (whole words, any case).
BUILTIN_ESCALATION_PHRASES: tuple[str, ...] = (
    "refund",
    "money back",
    "chargeback",
    "charge back",
    "lawyer",
    "legal action",
    "legal notice",
    "consumer court",
    "consumer forum",
    "sue you",
    "police",
    "fraud",
    "scam",
    "cheated",
    "talk to a human",
    "speak to a human",
    "talk to a person",
    "speak to a person",
    "real person",
    "talk to someone",
    "speak to someone",
    "your manager",
)


@dataclass(frozen=True)
class AnalysisFacts:
    """What check 6-8 and 11 need from the message's analysis (TR-AI-05)."""

    intent: str
    sentiment_score: float
    needs_human: bool
    needs_human_reason: str | None = None


@dataclass(frozen=True)
class PolicyInput:
    effective_mode: str
    auto_allowed: bool  # the plan's ai_modes include auto
    credits_available: bool  # the auto reply's credits fit in the period's quota
    paused_until: datetime | None
    now: datetime
    automation_handled: bool
    window_state: str
    analysis: AnalysisFacts | None
    message_text: str
    can_answer: bool
    confidence: float | None
    used_sources: int  # knowledge chunks the suggestion relied on
    top_similarity: float | None
    already_replied: bool  # an AI reply was already sent for this inbound message
    ai_replies_last_hour: int
    reply_text: str | None
    allowed_texts: Sequence[str]  # knowledge and brand settings (check 13)
    escalation_phrases: Sequence[str] = ()
    min_confidence: float = 0.75  # AUTO_MIN_CONFIDENCE
    min_similarity: float = 0.60  # AI_RETRIEVAL_MIN_SIM


@dataclass(frozen=True)
class Check:
    n: int
    name: str
    passed: bool
    value: str | float | bool | None = None
    outcome: Outcome = "skipped"  # what a failure means
    reason: str | None = None  # the code a failure records

    def as_json(self) -> dict[str, Any]:
        return {"n": self.n, "name": self.name, "passed": self.passed, "value": self.value}


@dataclass(frozen=True)
class Decision:
    outcome: Outcome
    reason: str | None
    checks: list[Check] = field(default_factory=list)

    @property
    def checks_json(self) -> list[dict[str, Any]]:
        return [c.as_json() for c in self.checks]

    @property
    def failed(self) -> Check | None:
        return next((c for c in self.checks if not c.passed), None)


def escalation_phrase(text: str, phrases: Sequence[str]) -> str | None:
    """The first built-in or workspace phrase in ``text`` (whole words, any case)."""
    normalized = normalize(text)
    for phrase in (*BUILTIN_ESCALATION_PHRASES, *phrases):
        wanted = normalize(phrase)
        if wanted and keyword_matches(normalized, wanted, "word"):
            return phrase
    return None


def _paused(value: datetime | None, now: datetime) -> bool:
    return value is not None and value > now


def evaluate(p: PolicyInput) -> Decision:
    """Run every check in order; the first failure decides (see the module docstring)."""
    a = p.analysis
    checks: list[Check] = [
        Check(1, "mode_is_auto", p.effective_mode == "auto", p.effective_mode, *SKIP_MODE),
        _plan_and_credits(p),
        _not_paused(p),
        Check(4, "no_automation", not p.automation_handled, p.automation_handled, *SKIP_HANDLED),
        Check(5, "window_open", p.window_state == "open", p.window_state, *ESC_WINDOW),
        _needs_human(a),
        _topic(a, p.message_text, p.escalation_phrases),
        _sentiment(a),
        Check(9, "can_answer", p.can_answer, p.can_answer, *ESC_KNOWLEDGE),
        _confidence(p),
        _grounded(a, p),
        _rate(p),
        _output(p.reply_text, p.allowed_texts),
    ]
    failed = next((c for c in checks if not c.passed), None)
    if failed is None:
        return Decision("auto_sent", None, checks)
    return Decision(failed.outcome, failed.reason, checks)


SKIP_MODE: tuple[Outcome, str] = ("skipped", "mode_not_auto")
SKIP_HANDLED: tuple[Outcome, str] = ("skipped", "automation_handled")
ESC_WINDOW: tuple[Outcome, str] = ("escalated", "window_closed")
ESC_KNOWLEDGE: tuple[Outcome, str] = ("escalated", "out_of_knowledge")


def _plan_and_credits(p: PolicyInput) -> Check:
    if not p.auto_allowed:
        value = "plan"
    elif not p.credits_available:
        value = "credits"
    else:
        value = "ok"
    return Check(2, "plan_and_credits", value == "ok", value, "skipped", "quota_exhausted")


def _not_paused(p: PolicyInput) -> Check:
    paused = _paused(p.paused_until, p.now)
    value = p.paused_until.isoformat() if paused and p.paused_until is not None else None
    return Check(3, "not_paused", not paused, value, "skipped", "paused")


def _sentiment(a: AnalysisFacts | None) -> Check:
    score = a.sentiment_score if a is not None else None
    passed = score is not None and score > NEGATIVE_SENTIMENT
    return Check(8, "sentiment", passed, score, "escalated", "negative_sentiment")


def _confidence(p: PolicyInput) -> Check:
    passed = p.confidence is not None and p.confidence >= p.min_confidence
    return Check(10, "confidence", passed, p.confidence, "escalated", "low_confidence")


def _needs_human(a: AnalysisFacts | None) -> Check:
    if a is None:
        return Check(6, "analysis_no_human", False, "no analysis", "escalated", "low_confidence")
    reason = a.needs_human_reason or "human_requested"
    return Check(
        6,
        "analysis_no_human",
        not a.needs_human,
        reason if a.needs_human else None,
        "escalated",
        reason,
    )


def _topic(a: AnalysisFacts | None, text: str, phrases: Sequence[str]) -> Check:
    intent = a.intent if a is not None else None
    if intent in ESCALATING_INTENTS:
        return Check(7, "no_escalation_topic", False, intent, "escalated", intent)
    phrase = escalation_phrase(text, phrases)
    if phrase is not None:
        return Check(7, "no_escalation_topic", False, phrase, "escalated", "policy_keyword")
    return Check(7, "no_escalation_topic", True, intent, "escalated", "policy_keyword")


def _grounded(a: AnalysisFacts | None, p: PolicyInput) -> Check:
    intent = a.intent if a is not None else None
    needs_source = intent in FACT_INTENTS
    grounded = p.used_sources > 0 and (p.top_similarity or 0.0) >= p.min_similarity
    return Check(
        11,
        "grounded_in_knowledge",
        grounded or not needs_source,
        p.top_similarity,
        "escalated",
        "out_of_knowledge",
    )


def _rate(p: PolicyInput) -> Check:
    capped = p.already_replied or p.ai_replies_last_hour >= MAX_AI_REPLIES_PER_HOUR
    value: str | float = "already replied" if p.already_replied else p.ai_replies_last_hour
    return Check(12, "rate", not capped, value, "skipped", "rate_capped")


def _output(reply: str | None, allowed: Sequence[str]) -> Check:
    finding = output_filter.check(reply or "", allowed)
    return Check(
        13,
        "output_filter",
        finding is None and bool(reply),
        finding.describe() if finding else (None if reply else "empty"),
        "escalated",
        "output_blocked",
    )
