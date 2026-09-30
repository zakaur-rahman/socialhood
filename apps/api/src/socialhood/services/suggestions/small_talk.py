"""Small talk needs no knowledge (C-062): greetings, thanks, goodbyes and "ok".

Seen live: a customer wrote "Hi"; the analysis said greeting, but the suggestion came back "Not in
your knowledge" with the gap "business information". suggest.v3 lets the model answer small talk
without knowledge (and never with a business fact); this module is the net under it:

- ``is_small_talk(text, intent)``: the whole message is small talk in English, Hindi or Hinglish
  (every word belongs to a known phrase, like "good morning", "thank you so much", "kya haal
  hai" or "धन्यवाद", or is "sir", "ji" and the like; punctuation and emoji may come with them,
  but emoji alone are left to the model), and its analysis, when there is one, gives it no
  business intent (greeting, feedback or other only: an "ok" the
  analysis reads as a purchase needs the model). "Hi, what's the price?" is not small talk.
- ``settle(draft, text, language)``: when the model still declines small talk, the suggestion
  offers a short fixed reply of the same kind (greeting, thanks, goodbye, acknowledgement) in the
  customer's language instead, so no knowledge gap is recorded. Devanagari text gets Hindi;
  Hinglish words, or Latin text the analysis calls Hindi, get Hinglish; anything else English.
  The texts state no fact, so FALLBACK_CONFIDENCE lets Auto send one like any confident reply
  (every other check of TR-AI-07 still applies).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import replace
from typing import Literal

from socialhood.services.suggestions.drafting import Draft

Kind = Literal["greeting", "thanks", "goodbye", "ack"]
Language = Literal["en", "hi", "hi-Latn"]

SMALL_TALK_INTENTS = frozenset({"greeting", "feedback", "other"})
FALLBACK_CONFIDENCE = 0.9  # a fixed, fact-free text: above AUTO_MIN_CONFIDENCE's default 0.75
MAX_WORDS = 12

# fmt: off
_PHRASES: dict[Kind | None, tuple[str, ...]] = {
    "greeting": (
        "hi", "hello", "hey", "hiya", "heya", "namaste", "namaskar", "namaskaram", "pranam",
        "ram ram", "salaam", "salam", "assalamualaikum", "asalamualaikum",
        "good morning", "good afternoon", "good evening", "gm",
        "how are you", "how are u", "how r u", "how r you", "how are you doing",
        "how is it going", "how s it going", "what s up", "whats up", "sup",
        "kaise ho", "kaise hain", "kaise hai", "aap kaise ho", "aap kaise hain", "kaise ho aap",
        "kaise hain aap", "kya haal hai", "kya hal hai", "kya haal", "kaisa hai",
        "sab badhiya", "sab theek",
        "नमस्ते", "नमस्कार", "प्रणाम", "राम राम", "हाय", "हेलो", "हैलो", "सुप्रभात",
        "कैसे हो", "कैसे हैं", "आप कैसे हैं", "आप कैसे हो", "क्या हाल है",
    ),
    "thanks": (
        "thanks", "thank you", "thank u", "thanku", "thankyou", "thanx", "thnx", "thnks", "thx",
        "ty", "tysm", "tq", "thanks a lot", "thank you so much", "thanks so much", "many thanks",
        "thank you very much", "shukriya", "dhanyavaad", "dhanyawad", "dhanyavad",
        "bahut shukriya", "bahut dhanyavaad",
        "धन्यवाद", "शुक्रिया", "थैंक यू", "थैंक्यू", "बहुत धन्यवाद", "बहुत शुक्रिया",
    ),
    "goodbye": (
        "bye", "goodbye", "good bye", "bye bye", "tata", "cya", "see you", "see ya",
        "take care", "talk later", "talk to you later", "have a nice day", "have a good day",
        "good night", "gn", "alvida", "phir milenge",
        "बाय", "अलविदा", "फिर मिलेंगे", "शुभ रात्रि",
    ),
    "ack": (
        "ok", "okay", "okey", "oki", "okie", "k", "alright", "all right", "fine", "cool",
        "great", "nice", "awesome", "perfect", "sure", "noted", "got it", "sounds good", "hmm",
        "accha", "acha", "achha", "theek", "theek hai", "thik", "thik hai", "ok ji", "haan",
        "han", "haan ji", "ji haan",
        "ओके", "ठीक", "ठीक है", "अच्छा", "हाँ", "हां", "जी हाँ", "जी हां",
    ),
    None: (  # allowed anywhere, never the message's kind
        "sir", "madam", "maam", "mam", "ji", "bhai", "bhaiya", "didi", "dear", "team", "there",
        "all", "everyone", "again", "bro", "friend", "so much", "a lot", "very", "and", "too",
        "also", "to you", "same to you", "you too",
        "जी", "सर", "भाई", "भैया", "दीदी", "मैडम",
    ),
}
_HINGLISH_WORDS = (
    "namaste", "namaskar", "namaskaram", "pranam", "ram", "salaam", "salam", "kaise", "kaisa",
    "haal", "hal", "kya", "aap", "hain", "hai", "ho", "sab", "badhiya", "theek", "thik",
    "shukriya", "dhanyavaad", "dhanyawad", "dhanyavad", "bahut", "alvida", "phir", "milenge",
    "tata", "accha", "acha", "achha", "haan", "han", "ji", "bhai", "bhaiya", "didi",
)
# fmt: on
# (English, Hinglish, Hindi) per kind: short, friendly, no business fact.
REPLIES: dict[Kind, tuple[str, str, str]] = {
    "greeting": (
        "Hi! How can I help you today?",
        "Namaste! Bataiye, hum aapki kya madad kar sakte hain?",
        "नमस्ते! बताइए, हम आपकी क्या मदद कर सकते हैं?",
    ),
    "thanks": (
        "You're welcome! Let us know if you need anything else.",
        "Aapka swagat hai! Kuch aur chahiye toh bataiye.",
        "आपका स्वागत है! कुछ और चाहिए तो बताइए।",
    ),
    "goodbye": (
        "Thanks for reaching out! Take care.",
        "Dhanyavaad! Apna khayal rakhiye.",
        "धन्यवाद! अपना ख़याल रखिए।",
    ),
    "ack": (
        "Great! Let us know if you need anything else.",
        "Theek hai! Kuch aur chahiye toh bataiye.",
        "ठीक है! कुछ और चाहिए तो बताइए।",
    ),
}
# Most telling first: "ok thanks bye" is a goodbye, "hi, thanks" a thanks.
_PRIORITY: tuple[Kind, ...] = ("goodbye", "thanks", "greeting", "ack")

# Words: letters and digits, and Devanagari with its vowel signs (not the danda, U+0964-5).
_WORD = re.compile(r"[\wऀ-ॣ०-ॿ]+")
_REPEATS = re.compile(r"(.)\1+")  # "hiii", "okkk", "thanksss", "byee"
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_JOINERS = dict.fromkeys(map(ord, "‌‍"))  # zero-width (non-)joiners in Hindi text


def _squeeze(word: str) -> str:
    return _REPEATS.sub(r"\1", word)


def _words(text: str) -> list[str]:
    normal = unicodedata.normalize("NFC", text).translate(_JOINERS).casefold()
    return [_squeeze(w) for w in _WORD.findall(normal)]


_HINGLISH = frozenset(_squeeze(word) for word in _HINGLISH_WORDS)
_TABLE: dict[tuple[str, ...], Kind | None] = {
    tuple(_words(phrase)): kind for kind, phrases in _PHRASES.items() for phrase in phrases
}
_LONGEST = max(len(key) for key in _TABLE)


def _kinds(words: list[str]) -> list[Kind | None] | None:
    """The phrases ``words`` splits into, as their kinds; None when some word belongs to none."""
    n = len(words)
    tail: list[list[Kind | None] | None] = [None] * n + [[]]
    for i in range(n - 1, -1, -1):
        for size in range(min(_LONGEST, n - i), 0, -1):
            key = tuple(words[i : i + size])
            rest = tail[i + size]
            if key in _TABLE and rest is not None:
                tail[i] = [_TABLE[key], *rest]
                break
    return tail[0]


def kind_of(text: str | None) -> Kind | None:
    """The kind of small talk the whole of ``text`` is, or None when it isn't only small talk.
    A message of emoji or punctuation alone is left to the model (an emoji can be angry)."""
    words = _words(text or "")
    if not words or len(words) > MAX_WORDS:
        return None
    kinds = _kinds(words)
    if kinds is None:
        return None
    found = set(kinds)
    return next((k for k in _PRIORITY if k in found), "greeting")  # "sir?" alone: a greeting


def is_small_talk(text: str | None, intent: str | None) -> bool:
    """See the module docstring. ``intent``: the message's analysed (or corrected) intent."""
    return (intent is None or intent in SMALL_TALK_INTENTS) and kind_of(text) is not None


def reply_language(text: str, language: str | None) -> Language:
    if _DEVANAGARI.search(text):
        return "hi"
    if _HINGLISH.intersection(_words(text)):
        return "hi-Latn"
    if language and language.casefold().split("-")[0] == "hi":
        return "hi-Latn"
    return "en"


def fallback_reply(text: str, language: str | None) -> str:
    english, hinglish, hindi = REPLIES[kind_of(text) or "greeting"]
    return {"en": english, "hi-Latn": hinglish, "hi": hindi}[reply_language(text, language)]


def settle(draft: Draft, text: str, language: str | None) -> Draft:
    """The draft for a small-talk message: the model's own reply when it gave one, else the
    fixed reply (never "can't answer", so no knowledge gap)."""
    if draft.can_answer and draft.reply:
        return draft
    return replace(
        draft,
        can_answer=True,
        reply=fallback_reply(text, language),
        missing_info=None,
        missing_topic=None,
        confidence=FALLBACK_CONFIDENCE,
        used_chunk_ids=[],
        blocked=None,
    )
