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


MC_OPTION_FLOOR = 0.01  # leave moderate mass on every option (template guidance)


def aggregate_multiple_choice(members: list[dict], options: list[str]) -> dict:
    """Per-option median across members, then floor + renormalize to sum 1.

    `members` is a list of {option_name: prob} dicts (each already ~normalized).
    Missing options are treated as 0 for that member. Returns
    {"probs": {opt: p}, "spread": <max per-option disagreement>, "n": <members>}.
    """
    members = [m for m in members if isinstance(m, dict) and m]
    if not members or not options:
        # uniform fallback
        u = 1.0 / len(options) if options else 0.0
        return {"probs": {o: u for o in options}, "spread": 0.0, "n": 0}

    per_opt = {o: [float(m.get(o, 0.0)) for m in members] for o in options}
    med = {o: _median(vals) for o, vals in per_opt.items()}
    spread = max((max(v) - min(v)) for v in per_opt.values())

    floored = {o: max(MC_OPTION_FLOOR, p) for o, p in med.items()}
    tot = sum(floored.values()) or 1.0
    probs = {o: p / tot for o, p in floored.items()}
    return {
        "probs": probs,
        "spread": spread,
        "needs_tiebreaker": spread >= TIEBREAK_SPREAD and len(members) >= 2,
        "n": len(members),
    }


def normalize_option_probs(raw: dict, options: list[str]) -> dict:
    """Coerce one member's raw per-option numbers into a clean distribution over
    exactly `options` (drop unknown keys, fill missing with 0, renormalize)."""
    vals = {}
    for o in options:
        v = raw.get(o)
        try:
            vals[o] = max(0.0, float(v))
        except (TypeError, ValueError):
            vals[o] = 0.0
    tot = sum(vals.values())
    if tot <= 0:
        u = 1.0 / len(options) if options else 0.0
        return {o: u for o in options}
    return {o: v / tot for o, v in vals.items()}
