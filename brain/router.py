"""Question router for sombra-bot.

The owner's forecasting brain is a structured actor / game-theory model. It is
the right instrument for questions whose outcome is *decided by actors making
choices* (elections, policy, court rulings, state/company action, conflict).
It is the WRONG instrument for *impersonal measurements* (commodity prices,
epidemiology, physical readings, market indices), which are better handled by
base-rate / reference-class / time-series reasoning.

This module classifies a question into one of those two lanes. It is pure
stdlib so it can be unit-tested with no API key and no heavy deps; an optional
LLM tiebreaker lives in `classify_with_llm` (used by the bot when the heuristic
is unsure).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

Lane = str  # "strategic" | "measurement"

# Outcome is produced by an actor's decision/action.
_STRATEGIC = [
    r"\bwill\s+[A-Z][\w.&-]+(?:\s+[A-Z][\w.&-]+)*\s+(announce|release|approve|sign|veto|resign|step down|withdraw|invade|attack|strike|ban|sanction|nominate|appoint|confirm|rule|vote|ratify|launch|acquire|merge|sue|indict|pardon|deploy|recognize|endorse)",
    r"\b(elect|election|re-?elect|coup|ceasefire|treaty|summit|referendum|impeach|no-confidence|coalition|verdict|ruling|lawsuit|indictment|sanction|tariff|strike|war|offensive|peace deal)\b",
    r"\b(president|prime minister|parliament|congress|senate|court|central bank|regulator|ministry|party|regime|OPEC|UN|NATO|EU|SEC|Fed|government)\b",
]
# Outcome is a number read off the world, not chosen by anyone.
_MEASUREMENT = [
    r"\bwhat\s+will\b.*\b(price|level|rate|index|average|value|number|count|total|settle|close|yield|share)\b",
    r"\b(futures?|settle|closing price|spot price|exchange rate|inflation|CPI|GDP|unemployment rate|temperature|rainfall|water level|tide|magnitude|wastewater|cases|deaths|box office|streams|downloads|subscribers)\b",
    r"\b(how many|how much|by how much)\b",
    r"\bgreater than|at least|exceed|above|below\b.*\b(\d|percent|%)\b",
]

_STRATEGIC_RE = [re.compile(p, re.I) for p in _STRATEGIC]
_MEASUREMENT_RE = [re.compile(p, re.I) for p in _MEASUREMENT]


@dataclass
class Routing:
    lane: Lane
    confidence: float  # 0..1; low => caller should use the LLM tiebreaker
    scores: dict
    reason: str


def classify_text(question_text: str, resolution_criteria: str = "",
                  question_type: str = "binary") -> Routing:
    """Heuristic lane classifier. `question_type` is Metaculus's type
    ("binary" | "multiple_choice" | "numeric" | "discrete" | "date")."""
    blob = f"{question_text}\n{resolution_criteria}"
    s = sum(bool(r.search(blob)) for r in _STRATEGIC_RE)
    m = sum(bool(r.search(blob)) for r in _MEASUREMENT_RE)

    # A numeric/date question is usually a measurement unless an actor verb is
    # clearly driving it; nudge, don't force.
    if question_type in ("numeric", "discrete", "date"):
        m += 1

    if s == 0 and m == 0:
        return Routing("strategic", 0.25, {"strategic": s, "measurement": m},
                       "no signal; default to strategic for LLM review")
    total = s + m
    if s >= m:
        conf = min(0.9, 0.5 + 0.1 * (s - m)) if s != m else 0.4
        return Routing("strategic", conf, {"strategic": s, "measurement": m},
                       f"{s} strategic vs {m} measurement signals")
    conf = min(0.95, 0.55 + 0.12 * (m - s))
    return Routing("measurement", conf, {"strategic": s, "measurement": m},
                   f"{m} measurement vs {s} strategic signals")


def classify(question) -> Routing:
    """Classify a forecasting_tools MetaculusQuestion (duck-typed)."""
    qtype = getattr(question, "question_type", None) or _infer_type(question)
    return classify_text(
        getattr(question, "question_text", "") or "",
        getattr(question, "resolution_criteria", "") or "",
        qtype,
    )


def _infer_type(question) -> str:
    name = type(question).__name__.lower()
    if "numeric" in name:
        return "numeric"
    if "date" in name:
        return "date"
    if "multiplechoice" in name or "multiple_choice" in name:
        return "multiple_choice"
    return "binary"
