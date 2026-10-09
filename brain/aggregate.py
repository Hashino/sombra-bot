"""Ensemble aggregation: median of member probabilities; a wide spread does not
get blindly averaged — it flags for a tiebreaker-judge synthesis (Pirohuni)."""
from __future__ import annotations

TIEBREAK_SPREAD = 0.30  # >= 30pp disagreement -> synthesize instead of median


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return 0.5
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def aggregate_binary(probs: list[float]) -> dict:
    probs = [p for p in probs if isinstance(p, (int, float))]
    if not probs:
        return {"prob": 0.5, "spread": 0.0, "needs_tiebreaker": False, "n": 0}
    spread = max(probs) - min(probs)
    return {
        "prob": _median(probs),
        "spread": spread,
        "needs_tiebreaker": spread >= TIEBREAK_SPREAD and len(probs) >= 2,
        "n": len(probs),
    }
