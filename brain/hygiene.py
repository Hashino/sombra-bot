"""Deterministic guardrails the LLM cannot talk itself out of (improvements
#20, #14). All pure stdlib → unit-testable with no API key.

- EVIDENCE banner: a hard, code-computed verdict on whether we actually have
  research. Prepended to the reasoning context so the falsification loop can't
  rationalize a real gap away, and surfaced in the public reasoning.
- date-before leakage filter: drop sources published AFTER a cutoff. A no-op in
  live forecasting (resolution is in the future) but keeps any future backtest
  honest, which is the only way our calibration numbers stay trustworthy.
"""
from __future__ import annotations

import re
from datetime import date, datetime

_PLACEHOLDER = "(no external research available)"
_MIN_USEFUL_CHARS = 200  # below this the "research" is effectively empty


def evidence_state(research: str | None) -> tuple[str, str]:
    """Return (level, banner). level ∈ {ok, thin, missing}. The banner is an
    authoritative line the LLM is told it may NOT override."""
    body = (research or "").strip()
    if not body or body == _PLACEHOLDER:
        return "missing", (
            "⚠ EVIDENCE MISSING (deterministic): no external research was "
            "retrieved for this question. Treat every specific claim as "
            "UNVERIFIED and stay close to the base rate; do not invent sources. "
            "This verdict is computed by code and cannot be overridden by reasoning."
        )
    if len(body) < _MIN_USEFUL_CHARS:
        return "thin", (
            "⚠ EVIDENCE THIN (deterministic): only a fragment of research was "
            "retrieved. Weight the base rate more heavily and flag low confidence. "
            "This verdict is computed by code and cannot be overridden by reasoning."
        )
    return "ok", ""


_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def _as_date(val) -> date | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        m = _ISO.search(val)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                return None
    return None


def drop_sources_after(text: str, cutoff, block_sep: str = "\n\n") -> str:
    """Drop research blocks whose latest ISO date is strictly after `cutoff`.

    A block with no detectable date is KEPT (we never silently discard
    undateable evidence). Splitting on blank lines matches how the searchers
    format one source per paragraph. Live: cutoff is the resolution date, which
    is in the future, so nothing is dropped — the filter only bites on backtests.
    """
    cutoff_d = _as_date(cutoff)
    if cutoff_d is None or not text:
        return text
    kept = []
    for block in text.split(block_sep):
        dates = [date(int(a), int(b), int(c)) for a, b, c in _ISO.findall(block)]
        dates = [d for d in dates if d is not None]
        if dates and max(dates) > cutoff_d:
            continue  # published after the cutoff → leakage, drop it
        kept.append(block)
    return block_sep.join(kept)
