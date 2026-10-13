"""Pre-gate detector for roleplay / persona / instruction-override jailbreaks.

Runs BEFORE the headroom gate. The headroom gate scores a query from a hash of
its text, so it has no notion of meaning; this detector adds a small, general,
documented rule set for a well-known jailbreak family:

  * persona adoption      ("pretend you are", "act as", "roleplay as", "you are now",
                           "in character", "from now on you are", "DAN", ...)
  * instruction override  ("ignore/disregard/forget (all) previous/prior instructions",
                           "new instructions:", "developer mode")
  * rule-free framing     ("as an AI without rules/limits/filters",
                           "no restrictions", "unfiltered", "jailbroken")

Text is normalized (Unicode NFKC, lowercased, punctuation -> space, whitespace
collapsed) before matching. Patterns are generic phrase families, not copies of
any test/battery string. Known limitation: lexical rules can be evaded by
paraphrase and can fire on benign requests that use the same phrasing
(e.g. "act as a translator").
"""
import re
import unicodedata

_PATTERNS = [
    ("persona: pretend", r"\bpretend (?:to be|you(?: are|re)?|that you)\b"),
    ("persona: act as", r"\b(?:act|behave|respond|answer|speak) (?:as|like) (?:if you (?:are|were) )?(?:an?|the|my)?\s*\w+"),
    ("persona: roleplay", r"\brole ?play(?:ing)?\b"),
    ("persona: you are now", r"\b(?:you are|you re|youre) now\b"),
    ("persona: from now on", r"\bfrom now on\b.*\b(?:you|your)\b"),
    ("persona: in character", r"\b(?:in|stay in|stay|break) character\b"),
    ("persona: DAN", r"\b(?:dan|do anything now)\b"),
    ("persona: simulate", r"\b(?:simulate|emulate|impersonate|play the (?:role|part) of)\b"),
    ("override: ignore instructions", r"\b(?:ignore|disregard|forget|override|bypass)\b(?: \w+){0,3} (?:instructions?|rules|guidelines|prompt|directives|programming)\b"),
    ("override: developer/jailbreak mode", r"\b(?:developer|god|jailbreak|jailbroken|unrestricted) mode\b|\bjailbr(?:oken|eak)\b"),
    ("rule-free framing", r"\b(?:without|no|free of|free from) (?:any )?(?:rules|restrictions|limits|limitations|filters|guidelines|safety limits|safeguards|censorship)\b"),
    ("rule-free framing: unfiltered", r"\b(?:unfiltered|uncensored|unrestricted)\b"),
]
_COMPILED = [(name, re.compile(p)) for name, p in _PATTERNS]


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def detect(text: str):
    """Return the matched rule name, or None if no jailbreak pattern matched."""
    n = normalize(text)
    for name, rx in _COMPILED:
        if rx.search(n):
            return name
    return None
