"""Structured follow-ups (VIS-11): what a run's ``hints`` say, in words.

A control on a visual (range, platform) or "Prepare replies" starts a new run in the same thread
with a ``RunHints`` instead of free text from the screen. Two texts come out of the same hints:

- ``bubble``: the member's question as readable words ("Same, for the last 90 days on
  Instagram"), stored as the run's ``request`` so the thread shows words, never ids;
- ``instruction``: what the planner is asked, built from whitelisted values only. The planner
  applies it as if the member had typed it. The question being repeated is the member's own
  earlier one, carried as data in quotes, never an instruction.

Nothing here reads data: the tools do, with the same role checks as any question.
"""

from __future__ import annotations

from socialhood.schemas.agent import RunHints

PLATFORM_WORDS = {
    "instagram": "Instagram",
    "facebook": "Facebook",
    "whatsapp": "WhatsApp",
}


def _controls(hints: RunHints) -> str:
    parts: list[str] = []
    if hints.range_days is not None:
        parts.append(f"for the last {hints.range_days} days")
    if hints.platform == "all":
        parts.append("across all platforms")
    elif hints.platform is not None:
        parts.append(f"on {PLATFORM_WORDS[hints.platform]}")
    return " ".join(parts)


def bubble(hints: RunHints) -> str:
    """The member's side of the thread: "Same, for the last 90 days on Instagram"."""
    if hints.reply_conversation_ids:
        return "Prepare replies for these leads"
    return f"Same, {_controls(hints)}"


def instruction(hints: RunHints, earlier_question: str | None) -> str:
    """The request the planner answers. ``earlier_question`` is the last question the member
    typed in this thread (None when it is out of the thread's context window)."""
    if hints.reply_conversation_ids:
        ids = ", ".join(str(i) for i in hints.reply_conversation_ids)
        return (
            "Prepare replies for these leads. Use draft_reply once for each of these "
            f"conversations, one at a time, and send nothing: {ids}. "
            "If a reply window is closed, skip that conversation and say so."
        )
    asked = hints.range_days is not None
    words = []
    if hints.range_days is not None:
        words.append(f'the range "the last {hints.range_days} days"')
    if hints.platform == "all":
        words.append("every platform (no platform filter)")
    elif hints.platform is not None:
        words.append(f'the platform "{hints.platform}"')
    change = " and ".join(words)
    which = (
        f'the member\'s earlier question, "{earlier_question}"'
        if earlier_question
        else "your previous answer's question"
    )
    return (
        f"The member changed a control on your last answer. Ask {which} again, with {change}, "
        "and keep everything else about it the same. Use the same tools, pass the range and the "
        "platform as tool arguments, and answer the same way."
        + ("" if asked else " Keep the range you used before.")
    )
