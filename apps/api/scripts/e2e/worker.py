"""The job worker as the end-to-end suite runs it (T9.4; apps/web/e2e). Test-only.

The normal worker (the launcher starts one per lane) with ``AI_PROVIDER=fake``, whose default reply
suggestion is "can't answer". The suite needs a reply it can send and edit (F-08), so the fake
answers every customer message with ``REPLY``, except a message containing ``UNKNOWN_MARK``,
which it can't answer (the "Not in your knowledge" card). The reply has no numbers or links, so
the output filter never withholds it. When the prompt carries a PRODUCTS line that matches the
question (GR-31), it answers with that variant's price and the product's link instead, as a
faithful model would. Nothing here reaches a model.

Usage: python worker.py [procrastinate worker options]
"""

from __future__ import annotations

import re
import sys
from typing import Any

from procrastinate import cli

from socialhood.ai.fake import FakeCall, FakeProvider
from socialhood.ai.registry import get_provider

REPLY = "Thanks for asking! Yes, it's in stock in every colour and ships this week."
UNKNOWN_MARK = "[e2e:unknown]"
TARGET = re.compile(r"^Customer \[TARGET\]: (.*)$", re.MULTILINE)
# GR-31: a faithful model reads the PRODUCTS lines it is given (services/catalogue/facts.py) and
# quotes the variant the question names, with the product's link.
PRODUCT = re.compile(r"\[p1\] (?P<name>[^|\n]+?) *(?:\||\n)")
LINK = re.compile(r"\[p1\][^\n]*link: (?P<link>\S+)")
MARKED = re.compile(
    r"  - (?P<variant>[^|\n]+)\|(?: SKU [^|\n]+\|)? price (?P<price>[^|\n]+)\|"
    r"[^\n]*matches the question"
)


def product_answer(text: str) -> dict[str, Any] | None:
    """The reply a model would write from the PRODUCTS block, or None when it names nothing."""
    product, link, marked = PRODUCT.search(text), LINK.search(text), MARKED.search(text)
    if product is None or link is None or marked is None:
        return None
    reply = (
        f"{product['name'].strip()} in {marked['variant'].strip()} is {marked['price'].strip()}. "
        f"{link['link']}"
    )
    return {
        "can_answer": True,
        "reply": reply,
        "missing_info": None,
        "missing_topic": None,
        "confidence": 0.95,
        "used_source_ids": ["p1"],
    }


def suggest(call: FakeCall) -> dict[str, Any]:
    text = "\n".join(turn.text for turn in call.contents)
    found = TARGET.search(text)
    if found is not None and UNKNOWN_MARK in found.group(1):
        return {
            "can_answer": False,
            "reply": None,
            "missing_info": "whether you offer gift wrapping",
            "missing_topic": "gift wrapping",
            "confidence": 0.2,
            "used_source_ids": [],
        }
    if (answer := product_answer(text)) is not None:
        return answer
    return {
        "can_answer": True,
        "reply": REPLY,
        "missing_info": None,
        "missing_topic": None,
        "confidence": 0.9,
        "used_source_ids": [],
    }


def main() -> None:
    provider = get_provider()
    if not isinstance(provider, FakeProvider):
        raise SystemExit("The e2e worker needs AI_PROVIDER=fake")
    provider.respond("suggest", suggest)
    sys.argv = ["procrastinate", "--app=socialhood.jobs.app.app", "worker", *sys.argv[1:]]
    cli.main()  # type: ignore[no-untyped-call]


if __name__ == "__main__":
    main()
