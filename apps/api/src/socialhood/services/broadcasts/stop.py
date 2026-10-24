"""STOP replies (GR-23): the messages that withdraw a customer's marketing consent.

One list, kept here so the product and its tests read the same words. A message counts only when
the whole message, after the clean-up below, is one of these phrases: "stop" alone, not "please
don't stop the delivery" or "stop by tomorrow". Matching the whole message is deliberately
strict; a customer whose wording is not on the list can still be opted out by hand on the
contact. *Unverified: whether Meta or Indian rules require particular words (O-11 covers the
legal check); this is the usual set plus common Hindi and Hinglish forms.*

Clean-up before matching: lower case, the Devanagari and Latin punctuation and emoji dropped,
spaces collapsed, and polite fillers (please, pls, kindly, now, thanks, ...) removed from the ends.

- English: stop, stop all, stopall, unsubscribe, unsub, opt out, optout, cancel, end, quit,
  remove me, remove me from the list, no more messages, do not message me, dont message me,
  do not contact me, dont contact me, stop messaging me, stop sending messages.
- Hinglish: band karo, band kar do, band kardo, bandh karo, mat bhejo, mat bhejiye, message mat
  bhejo, msg mat bhejo, bhejna band karo, messages band karo, nahi chahiye.
- Hindi (Devanagari): बंद करो, बंद करें, बंद, मत भेजो, मैसेज मत भेजो, स्टॉप, अनसब्सक्राइब.
"""

from __future__ import annotations

import re
import unicodedata

# Words that may sit around a phrase without changing what it means.
FILLERS = frozenset(
    {"please", "pls", "plz", "kindly", "now", "thanks", "thank", "you", "ok", "okay", "kripya"}
)

PHRASES = frozenset(
    {
        # English
        "stop",
        "stop all",
        "stopall",
        "unsubscribe",
        "unsubscribe me",
        "unsub",
        "opt out",
        "optout",
        "cancel",
        "end",
        "quit",
        "remove me",
        "remove me from the list",
        "no more messages",
        "do not message me",
        "dont message me",
        "do not contact me",
        "dont contact me",
        "stop messaging me",
        "stop sending messages",
        # Hinglish
        "band karo",
        "band kar do",
        "band kardo",
        "bandh karo",
        "mat bhejo",
        "mat bhejiye",
        "message mat bhejo",
        "msg mat bhejo",
        "bhejna band karo",
        "messages band karo",
        "nahi chahiye",
        # Hindi
        "बंद करो",
        "बंद करें",
        "बंद",
        "मत भेजो",
        "मैसेज मत भेजो",
        "स्टॉप",
        "अनसब्सक्राइब",
    }
)

_APOSTROPHES = re.compile(r"['\u2019\u2018`]")
_SPACES = re.compile(r"\s+")
# Invisible marks that change how a character is drawn, not what is said: an emoji's variation
# selector, zero-width spaces and joiners. They are dropped, not turned into spaces.
_INVISIBLE = {ord(chr(c)): None for c in (0xFE0E, 0xFE0F, 0x200B, 0x200C, 0x200D)}


def normalize(text: str) -> str:
    """The message as compared: lower case, only letters, digits and Devanagari marks kept (other
    characters become spaces), fillers dropped, spaces collapsed."""
    folded = unicodedata.normalize("NFKC", text).casefold().translate(_INVISIBLE)
    lowered = _APOSTROPHES.sub("", folded)
    kept = "".join(ch if unicodedata.category(ch)[0] in ("L", "N", "M") else " " for ch in lowered)
    words = [w for w in _SPACES.split(kept.strip()) if w]
    while words and words[0] in FILLERS:
        words.pop(0)
    while words and words[-1] in FILLERS:
        words.pop()
    return " ".join(words)


def is_stop(text: str | None) -> bool:
    """Whether a customer's message is a request to stop marketing messages."""
    if not text or len(text) > 120:
        return False
    return normalize(text) in PHRASES
