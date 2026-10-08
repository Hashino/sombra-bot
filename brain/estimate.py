"""Deterministic probability composition + calibration.

The LLM supplies the *ingredients* of the estimate (a base rate, the
independent routes to YES with each route's probability, a blocker probability,
and how much to trust the inside view). This module does the ARITHMETIC. That
is the point of improvement #1: the final number comes from a reproducible
calculation over elicited probabilities, not from an LLM eyeballing a percent.

All pure stdlib → unit-testable with no API key.
"""
from __future__ import annotations

import json
import re


def _clamp(x: float, lo: float, hi: float) -> float:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, x))


def noisy_or(ps: list[float]) -> float:
    """P(at least one independent route fires)."""
    prod = 1.0
    for p in ps:
        prod *= (1.0 - _clamp(p, 0.0, 1.0))
    return 1.0 - prod


def compose(prior: float, yes_path_ps: list[float], blocker_p: float,
            inside_confidence: float) -> float:
    """Inside view (routes to YES, minus a blocker) blended with the base-rate prior.
    `inside_confidence` is how much weight the structural model earns vs the prior."""
    prior = _clamp(prior, 0.0, 1.0)
    if yes_path_ps:
        p_inside = noisy_or(yes_path_ps) * (1.0 - _clamp(blocker_p, 0.0, 1.0))
    else:
        p_inside = prior
    w = _clamp(inside_confidence, 0.20, 0.85)  # never fully trust or ignore the model
    return _clamp(w * p_inside + (1.0 - w) * prior, 0.0, 1.0)


def calibrate(raw: float, days_to_resolution: float | None) -> float:
    """Correct LLM overconfidence: pull toward 0.5, more for longer horizons.
    Constants are provisional — to be tuned against MiniBench results."""
    d = 30.0 if days_to_resolution is None else max(0.0, float(days_to_resolution))
    pull = _clamp(0.05 + 0.25 * (min(d, 180.0) / 180.0), 0.05, 0.30)
    cal = raw + pull * (0.5 - raw)
    return _clamp(cal, 0.02, 0.98)


def parse_estimate(text: str) -> dict | None:
    """Robustly pull the JSON estimate object out of an LLM reply."""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.I | re.M).strip()
    m = re.search(r"\{.*\}", t, flags=re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def estimate_probability(parsed: dict, days_to_resolution: float | None) -> tuple[float, str]:
    """Turn the elicited ingredients into a calibrated probability + an audit trail."""
    prior = _clamp(parsed.get("base_rate", 0.5), 0.0, 1.0)
    paths = parsed.get("yes_paths") or []
    path_ps = []
    for p in paths:
        if isinstance(p, dict):
            path_ps.append(_clamp(p.get("p", 0.0), 0.0, 1.0))
        else:
            path_ps.append(_clamp(p, 0.0, 1.0))
    blocker = _clamp(parsed.get("blocker_p", 0.0), 0.0, 1.0)
    conf = _clamp(parsed.get("inside_confidence", 0.5), 0.0, 1.0)

    raw = compose(prior, path_ps, blocker, conf)
    final = calibrate(raw, days_to_resolution)

    breakdown = (
        "STRUCTURED ESTIMATE (computed, not guessed):\n"
        f"- base rate (outside view): {prior:.0%}\n"
        f"- routes to YES (p each): {', '.join(f'{x:.0%}' for x in path_ps) or 'none'}\n"
        f"- P(any route) via noisy-OR: {noisy_or(path_ps):.0%}\n"
        f"- blocker probability: {blocker:.0%}\n"
        f"- inside-view weight: {_clamp(conf,0.20,0.85):.0%}\n"
        f"- blended raw: {raw:.1%}\n"
        f"- after calibration (horizon {days_to_resolution if days_to_resolution is not None else '~30'}d): {final:.1%}"
    )
    return final, breakdown
