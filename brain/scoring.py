"""Forecast scoring — the pure, API-free core of the backtest (improvement #5,
backtest half). Runs the bot over already-resolved HISTORICAL questions and
measures whether it is any good — crucially, whether the actor/game-theory lens
actually EARNS its place or just adds correlated noise.

Metaculus scores: we implement the two that matter for ranking.
- Baseline score: 100·(1 + log2(p_outcome)). 0 for an uninformative 50%, +100
  for a confident correct call, negative for confident-and-wrong. This is the
  tournament's own yardstick.
- Brier: (p − outcome)². Lower is better; strictly proper, easy to average.
Plus a calibration curve + ECE so we can SEE over/under-confidence, which is the
exact failure mode the single-lens methodology risks.

Pure stdlib → unit-tested with no API key.
"""
from __future__ import annotations

import math

_EPS = 1e-6


def _clamp01(p: float) -> float:
    return max(_EPS, min(1.0 - _EPS, float(p)))


def brier_binary(prob: float, outcome: int) -> float:
    """(p − y)², y ∈ {0,1}. Lower is better."""
    return (float(prob) - float(outcome)) ** 2


def baseline_binary(prob: float, outcome: int) -> float:
    """Metaculus baseline score for a binary forecast, in points."""
    p_out = _clamp01(prob if outcome else 1.0 - prob)
    return 100.0 * (1.0 + math.log2(p_out))


def log_score_binary(prob: float, outcome: int) -> float:
    """Natural-log score of the mass on the realized outcome (higher = better)."""
    return math.log(_clamp01(prob if outcome else 1.0 - prob))


def brier_mc(probs: dict, winner: str) -> float:
    """Multiclass Brier: Σ_o (p_o − 1[o=winner])². Lower is better."""
    return sum((float(p) - (1.0 if o == winner else 0.0)) ** 2
               for o, p in probs.items())


def baseline_mc(probs: dict, winner: str, n_options: int | None = None) -> float:
    """Metaculus baseline for multiple choice: 100·(1 + log_N(p_winner)), where
    N is the option count (so an uniform guess scores 0)."""
    n = n_options or len(probs)
    if n < 2:
        return 0.0
    p_win = _clamp01(float(probs.get(winner, 0.0)))
    return 100.0 * (1.0 + math.log(p_win) / math.log(n))


def calibration_curve(pairs: list[tuple[float, int]], n_bins: int = 10) -> list[dict]:
    """Group (prob, outcome) into equal-width bins; per bin return predicted mean
    confidence vs observed frequency. Reveals systematic over/under-confidence."""
    bins = [[] for _ in range(n_bins)]
    for p, y in pairs:
        idx = min(n_bins - 1, int(_clamp01(p) * n_bins))
        bins[idx].append((float(p), float(y)))
    out = []
    for i, b in enumerate(bins):
        if not b:
            out.append({"bin": i, "n": 0, "conf": None, "freq": None})
            continue
        conf = sum(p for p, _ in b) / len(b)
        freq = sum(y for _, y in b) / len(b)
        out.append({"bin": i, "n": len(b), "conf": conf, "freq": freq})
    return out


def expected_calibration_error(pairs: list[tuple[float, int]], n_bins: int = 10) -> float:
    """ECE = Σ (n_b/N)·|freq_b − conf_b|. 0 = perfectly calibrated."""
    if not pairs:
        return 0.0
    n = len(pairs)
    ece = 0.0
    for b in calibration_curve(pairs, n_bins):
        if b["n"] and b["conf"] is not None:
            ece += (b["n"] / n) * abs(b["freq"] - b["conf"])
    return ece


def summarize_binary(records: list[dict]) -> dict:
    """records: [{"prob": p, "outcome": 0/1, "community": p_or_None, "method": str}].
    Returns mean Brier / baseline / ECE for the bot, the community baseline when
    present, and the bot's EDGE over the community (the number that actually says
    whether we belong in the tournament)."""
    rs = [r for r in records if r.get("prob") is not None and r.get("outcome") is not None]
    if not rs:
        return {"n": 0}
    pairs = [(r["prob"], int(r["outcome"])) for r in rs]
    out = {
        "n": len(rs),
        "brier": sum(brier_binary(p, y) for p, y in pairs) / len(rs),
        "baseline": sum(baseline_binary(p, y) for p, y in pairs) / len(rs),
        "ece": expected_calibration_error(pairs),
    }
    comm = [r for r in rs if r.get("community") is not None]
    if comm:
        cb = sum(baseline_binary(r["community"], int(r["outcome"])) for r in comm) / len(comm)
        bb = sum(baseline_binary(r["prob"], int(r["outcome"])) for r in comm) / len(comm)
        out["community_baseline"] = cb
        out["edge_over_community"] = bb - cb  # >0 means we beat the crowd
        out["n_vs_community"] = len(comm)
    return out


def summarize_by_method(records: list[dict]) -> dict:
    """Mean baseline per aggregation method tag — the lens-value question: does
    'tiebreaker-judge' or 'actor-heavy' actually outscore the plain median?"""
    groups: dict[str, list[dict]] = {}
    for r in records:
        groups.setdefault(r.get("method", "?"), []).append(r)
    return {k: summarize_binary(v) for k, v in groups.items()}
