"""First-boot onboarding: Jarvis meets its user. Spoken, one question at
a time, never a form read aloud (requirement 2). First boot asks only the
essentials — what to be called, and how to say it right — and says, in
character, that it learns everything else as it goes.

The mechanics live here; the brain wires them to speech.say + dialog.listen
+ transcript answers. Name extraction is rule-first, LLM-fallback."""

from __future__ import annotations

import re
from typing import Optional

# Rule-based name extraction. Order matters: explicit phrasings first.
_PATTERNS = [
    re.compile(r"\bcall me\s+([A-Za-z][\w'’-]*)", re.IGNORECASE),
    re.compile(r"\bmy name(?:'s| is)\s+([A-Za-z][\w'’-]*)", re.IGNORECASE),
    re.compile(r"\bi'?m\s+([A-Za-z][\w'’-]*)", re.IGNORECASE),
    re.compile(r"\bit'?s\s+([A-Za-z][\w'’-]*)", re.IGNORECASE),
]

_STOPWORDS = {
    "yes", "no", "yeah", "nope", "not", "sorry", "sure", "okay", "ok",
    "hello", "hi", "hey", "the", "a", "an", "good", "fine", "well",
}


def extract_name(text: str) -> Optional[str]:
    """Best-effort name from a spoken answer. Returns a capitalized name
    or None (caller falls back to the LLM, then to re-asking)."""
    for pat in _PATTERNS:
        if m := pat.search(text):
            cand = m.group(1)
            if cand.lower() not in _STOPWORDS:
                return cand.capitalize()
    # bare single-word answer ("Ofek")
    words = re.findall(r"[A-Za-z][\w'’-]*", text)
    if len(words) == 1 and words[0].lower() not in _STOPWORDS:
        return words[0].capitalize()
    return None


# Spoken scripts. Kept here (mechanics), not in personality/ — the
# CHARACTER comes from system.md; these are the interview's stage marks.
INTRO = (
    "Hello. I'm Jarvis — this machine's assistant. We haven't met, so I "
    "don't know anything about you yet, but I learn as we go. To start: "
    "what should I call you?"
)


def confirm_pronunciation(name: str) -> str:
    return f"{name}. Did I say that right?"


def ask_again() -> str:
    return "Sorry — I didn't catch a name. What should I call you?"


def welcome(name: str) -> str:
    return (
        f"Good to meet you, {name}. I'll pick up the rest as we go — "
        "you can always correct me. What can I do for you?"
    )


# A late correction of the name, at any time, in any session.
_CORRECTION = re.compile(
    r"\b(?:actually,?\s+)?(?:call me|my name(?:'s| is)|it'?s (?:pronounced|actually))\s+"
    r"([A-Za-z][\w'’-]*)",
    re.IGNORECASE,
)


def detect_name_correction(text: str) -> Optional[str]:
    if m := _CORRECTION.search(text):
        cand = m.group(1)
        if cand.lower() not in _STOPWORDS:
            return cand.capitalize()
    return None
