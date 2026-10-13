"""Content-grounded residual r_H for a query (TASK-05; replaces the sha256-derived residual).

Method (transparent scoring rule, no model, no hash):
  1. Normalize the text (Unicode NFKC, lowercase, punctuation -> space).
  2. Detect FEATURE FAMILIES taken from the public prompt-injection / jailbreak
     taxonomy (OWASP LLM01 Prompt Injection; Perez & Ribeiro 2022 "Ignore
     Previous Prompt"; Wei et al. 2023 "Jailbroken": prefix injection, refusal
     suppression, role-play, base64 / translation obfuscation):
       base cues   -- a single cue on its own (low weight; benign text uses them too)
         control_surface_strong  references to the assistant's own control layer
                                 (system prompt, prior instructions, refusal,
                                 guardrails, filters, hidden fields, jailbreak ...)
         control_surface_weak    generic words (safety, rules, policy, secret ...)
         override                subversion verbs (ignore, bypass, disable ...) and
                                 rule-free framing (no limits, unfiltered ...)
         exfiltration            disclosure verbs / exact-copy cues (reveal, leak,
                                 verbatim, exact, word for word ...)
         persona                 role adoption (pretend, roleplay, act as ...)
         obfuscation             encodings (base64, rot13, hex, cipher ...)
         counterfactual          hypothetical framing (hypothetically, imagine ...)
       attack structures -- an operation AIMED AT the control surface (high weight;
                            the "->control" structures need a STRONG reference)
         override->control       override cue + control-surface reference
         exfiltrate->control     exfiltration cue + control-surface reference
         persona->rule-free      persona + override/control/compliance cue
         obfuscate->control      encoding/transform + control/override cue
         transform-then-execute  "translate/decode ... then execute/run/follow"
         prefix injection        "repeat after me", "say exactly", "start your reply with"
         unconditional comply    "comply with everything", "answer anything",
                                 "never refuse", "no matter what"
         counterfactual->control hypothetical framing + control-surface reference
  3. Combine fired families with a noisy-OR:  score = 1 - prod(1 - w_f).
     The score is in [0, 1]; 0 = no injection features (benign reference profile).

Wiring into the Howard residual: the benign reference profile predicts zero
injection features, so the gate is fed the pair (d, D_K) = (score, 0.0); the
Howard mismatch d - lambda*D_K is then exactly the score, i.e. r_H = score.

Patterns are general phrase families, not copies of any calibration or battery
string (tests/test_query_residual.py checks the battery strings are absent).
Known limitation: this is lexical. Paraphrases that avoid every family (e.g.
indirect extraction questions) score 0 and are admitted; see the held-out
results in README / TASK-05 report.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Tuple


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).lower()
    t = t.replace("'", "").replace("\u2019", "")  # don't -> dont, you're -> youre
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _rx(*alts: str) -> "re.Pattern[str]":
    return re.compile(r"\b(?:" + "|".join(alts) + r")\b")


# ---- base cue lexicons ------------------------------------------------------
_RULE_FREE = _rx(
    r"(?:no|without|zero|free of|free from) (?:any )?(?:safety |ethical |content )?"
    r"(?:limits|limitations|restrictions|rules|filters?|guardrails|safeguards|censorship|ethics|boundaries|guidelines)",
    r"unfiltered", r"uncensored", r"unrestricted", r"jailbroken",
)
_CONTROL_STRONG = _rx(
    r"system (?:prompt|message|instructions?)",
    r"(?:previous|prior|earlier|original|initial|above) (?:instructions?|prompts?|rules|directives|guidance|messages?)",
    r"(?:your|its|the models?|the assistants?) (?:instructions|rules|guidelines|programming|configuration|config|policies|policy|filters?|restrictions|guardrails|safeguards|training)",
    r"hidden (?:fields?|instructions?|prompts?|data|text|messages?|content|configuration|config)",
    r"refusals?", r"guardrails?", r"safeguards?", r"content filters?", r"safety (?:limits|filters?|layer|checks|settings|guardrails)",
    r"jailbreak\w*", r"developer mode", r"god mode", r"censorship",
    r"everything above", r"above this line",
)
_CONTROL_WEAK = _rx(
    r"safety", r"rules", r"guidelines", r"polic(?:y|ies)", r"instructions?", r"prompts?",
    r"secrets?", r"hidden", r"internal", r"confidential", r"restrictions", r"filters?",
    r"password", r"configuration", r"ethics",
)
_OVERRIDE = _rx(
    r"ignore", r"disregard", r"forget", r"override", r"bypass", r"circumvent", r"evade",
    r"disable", r"deactivate", r"turn off", r"switch off", r"get around", r"lift",
    r"(?:were|was|is|are|been|being|got) (?:disabled|removed|turned off|lifted|switched off|off)",
)
_EXFIL = _rx(
    r"reveal", r"leak", r"dump", r"expose", r"divulge", r"disclose", r"exfiltrate",
    r"verbatim", r"word for word", r"exact", r"exactly", r"in full", r"full text", r"raw",
)
_PERSONA = _rx(
    r"pretend", r"role ?play\w*", r"act as", r"act like", r"you are now", r"youre now",
    r"from now on you", r"simulate", r"impersonate", r"in character", r"play the (?:role|part) of",
    r"stay in character",
)
_OBFUSCATION = _rx(r"base ?64", r"rot ?13", r"hex(?:adecimal)?", r"cipher", r"encode", r"encrypt", r"obfuscate")
_COUNTERFACTUAL = _rx(r"hypothetical(?:ly)?", r"imagine", r"suppose", r"what if", r"in a world where",
                      r"in a fictional", r"lets say")

# ---- attack structures (cue sequences, not single words) --------------------
_TRANSFORM_EXECUTE = re.compile(
    r"\b(?:translate|decode|convert|rewrite|encode|decrypt)\b.*\b(?:then|and)\b.*"
    r"\b(?:execute|run|follow|obey|carry out|act on|do what it says)\b")
_PREFIX_INJECTION = _rx(r"repeat after me", r"say exactly", r"say the following",
                        r"(?:start|begin) your (?:reply|answer|response) with",
                        r"respond only (?:with|in)", r"reply only (?:with|in)")
_UNCONDITIONAL = _rx(
    r"(?:comply|obey) with (?:everything|anything|all)", r"(?:answer|do|say|tell me) anything",
    r"answers? (?:anything|everything)", r"anything i ask", r"never (?:refuse|decline|say no)",
    r"(?:dont|do not|cannot|cant|wont) (?:refuse|decline)", r"no matter what",
    r"always (?:comply|say yes|agree|obey)", r"do anything now",
)

# Weights. Base cues are deliberately low so a benign query that merely uses one
# of these words stays far below epsilon_H; attack structures are high.
WEIGHTS: Dict[str, float] = {
    "control_surface_strong": 0.20,
    "control_surface_weak": 0.05,
    "override": 0.10,
    "exfiltration": 0.10,
    "persona": 0.25,
    "obfuscation": 0.10,
    "counterfactual": 0.05,
    "override->control": 0.70,
    "exfiltrate->control": 0.60,
    "persona->rule-free": 0.60,
    "obfuscate->control": 0.60,
    "transform-then-execute": 0.50,
    "prefix_injection": 0.45,
    "unconditional_compliance": 0.50,
    "counterfactual->control": 0.40,
}


def features(text: str) -> List[str]:
    """Return the names of the feature families that fire on `text`."""
    n = normalize(text)
    rule_free = bool(_RULE_FREE.search(n))
    cs_strong = rule_free or bool(_CONTROL_STRONG.search(n))
    cs_weak = bool(_CONTROL_WEAK.search(n))
    override = rule_free or bool(_OVERRIDE.search(n))
    exfil = bool(_EXFIL.search(n))
    persona = bool(_PERSONA.search(n))
    transform_exec = bool(_TRANSFORM_EXECUTE.search(n))
    obfus = bool(_OBFUSCATION.search(n)) or transform_exec
    counterf = bool(_COUNTERFACTUAL.search(n))
    prefix = bool(_PREFIX_INJECTION.search(n))
    uncond = bool(_UNCONDITIONAL.search(n))

    fired = []
    if cs_strong:
        fired.append("control_surface_strong")
    elif cs_weak:
        fired.append("control_surface_weak")
    for name, on in (("override", override), ("exfiltration", exfil), ("persona", persona),
                     ("obfuscation", obfus), ("counterfactual", counterf)):
        if on:
            fired.append(name)
    # attack structures require a STRONG control-surface reference: generic words
    # (safety, rules, policy) are ambiguous about whose rules ("turn off safety mode
    # on my car", "the exact rules of chess") and only add the low base weight
    if override and cs_strong:
        fired.append("override->control")
    if exfil and cs_strong:
        fired.append("exfiltrate->control")
    if persona and (override or cs_strong or uncond):
        fired.append("persona->rule-free")
    if obfus and (cs_strong or override):
        fired.append("obfuscate->control")
    if transform_exec:
        fired.append("transform-then-execute")
    if prefix:
        fired.append("prefix_injection")
    if uncond:
        fired.append("unconditional_compliance")
    if counterf and cs_strong:
        fired.append("counterfactual->control")
    return fired


def score(text: str) -> Tuple[float, List[str]]:
    """Noisy-OR injection score in [0, 1] and the fired feature families."""
    fired = features(text)
    keep = 1.0
    for f in fired:
        keep *= 1.0 - WEIGHTS[f]
    return 1.0 - keep, fired


def howard_pairs(text: str) -> List[Tuple[float, float]]:
    """(d, D_K) pairs for HowardResidual: observed score vs benign reference 0.0 -> r_H = score."""
    s, _ = score(text)
    return [(s, 0.0)]
