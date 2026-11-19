"""Comments that need no AI reading (YT4): emoji only, tags only, or a short hello or praise made
only of listed words ("nice", "great video", "bahut badhiya 🔥"). They're read by these rules, at
no credit, and stored like any analysis (model ``rules``).

Only a comment made ENTIRELY of known parts is caught. Anything else goes to the AI: a question
mark, a digit or link, a word off the lists ("nice, how much", "not good"), a negative or unclear
emoji (😡 🙄 🤔), or more than MAX_WORDS words. Add words to the lists below, never patterns.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

MAX_CHARS = 120
MAX_WORDS = 6


def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


# A hello, thanks or a name for the creator: a greeting, neutral.
GREETING_WORDS = _words(
    """hi hii hello helo hey heyy yo namaste namaskar salam salaam assalamualaikum hola first
    bro bhai brother sis sister didi sir mam maam madam ji dear guys everyone all team
    morning evening night"""
)
# Praise, in English, Hindi and Hinglish: feedback, positive.
PRAISE_WORDS = _words(
    """nice great awesome amazing wow woww cool love loved loving lovely beautiful superb
    excellent perfect best fantastic wonderful brilliant outstanding fire lit gorgeous cute good
    op osm awsm epic legend goat beast blowing informative helpful useful rocking keep
    thanks thank thankyou thx ty congrats congratulations bravo yay omg wah waah
    gajab mast badhiya badiya bdhiya accha acha achha sundar kamaal kamal zabardast jabardast
    shandar shandaar mashallah masha subhanallah bless blessed"""
)
# Words that only join the others: never enough on their own ("this is it" goes to the AI).
FILLER_WORDS = _words(
    """it up going on the a an so very too much this is was of video videos content work job
    post reel short shorts channel really just always you your u ur my all time mind god allah
    bahut bohot bht hai he h and"""
)
WORDS = GREETING_WORDS | PRAISE_WORDS | FILLER_WORDS

POSITIVE_EMOJI = frozenset(
    "❤🧡💛💚💙💜🖤🤍🤎💖💗💓💞💕💘💝😍🥰😘🤩🔥👏🙌👍💯✨🌟⭐😊😁😀😃😄🥳🎉🎊👌💪🫶🙏🤗☺😇🏆🥇"
)
SKIN_AND_JOINERS = frozenset("‍️︎") | {chr(c) for c in range(0x1F3FB, 0x1F400)}
ALLOWED_PUNCTUATION = frozenset("!.,~-")

_WORD = re.compile(r"[^\W\d_]+")
_MENTION = re.compile(r"@[\w.]+")
_REPEATS = re.compile(r"(.)\1{2,}")


@dataclass(frozen=True)
class RuleReading:
    sentiment: str  # "positive" | "neutral"
    sentiment_score: float
    intent: str  # "feedback" | "greeting" | "other"


def _known(word: str) -> str | None:
    """The listed form of ``word``, stretched letters folded: "niceee" -> "nice"."""
    for variant in (word, _REPEATS.sub(r"\1\1", word), _REPEATS.sub(r"\1", word)):
        if variant in WORDS:
            return variant
    return None


def reading(text: str | None) -> RuleReading | None:
    """The rules' reading of a comment, or None when the AI should read it."""
    text = unicodedata.normalize("NFKC", text or "").casefold().strip()
    if not text or len(text) > MAX_CHARS:
        return None
    mentions = _MENTION.findall(text)
    rest = _MENTION.sub(" ", text)
    words: list[str] = []
    emoji = False
    for token in rest.split():
        for part in re.split(r"([^\W\d_]+)", token):
            if not part:
                continue
            if _WORD.fullmatch(part):
                known = _known(part)
                if known is None:
                    return None
                words.append(known)
                continue
            for char in part:
                if char in ALLOWED_PUNCTUATION or char in SKIN_AND_JOINERS:
                    continue
                if char in POSITIVE_EMOJI:
                    emoji = True
                    continue
                return None  # a digit, "?", a link's ":" or "/", or an emoji we don't read
    if len(words) > MAX_WORDS:
        return None
    if not words and not emoji:
        return RuleReading("neutral", 0.0, "other") if mentions else None
    if any(w in PRAISE_WORDS for w in words):
        return RuleReading("positive", 0.7, "feedback")
    if emoji:
        return RuleReading("positive", 0.6, "greeting")
    if any(w in GREETING_WORDS for w in words):
        return RuleReading("neutral", 0.1, "greeting")
    return None  # only joining words
