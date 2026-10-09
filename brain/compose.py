"""Binary probability composition + the answer-space witness (self-check).

Coherent single composition path (we deliberately dropped the Monte-Carlo-code
lane and raw noisy-OR-only): an actor question resolves YES through a set of
BRANCHES (mutually-exclusive scenarios) — P(YES)=Σ w_i·P(YES|branch_i) — or, for
simple independent routes, a noisy-OR. Prediction-market prices enter only as a
FLOOR/CEILING (never a raw anchor). The inside view is blended with the sealed
base rate by an inside-confidence weight. Finally the WITNESS: the member also
states, independently, where its probability mass sits; if that disagrees with
what its structured ingredients compute, we distrust the structured number and
fall back toward the base rate (and flag it). Pure stdlib → unit-testable.
"""
from __future__ import annotations

from .estimate import _clamp, noisy_or, calibrate, parse_estimate  # reuse


def _branch_mixture(branches: list[dict]) -> float | None:
    rows = [(float(b.get("w", 0)), _clamp(b.get("p_yes", 0), 0, 1))
            for b in branches if isinstance(b, dict)]
    rows = [(w, p) for w, p in rows if w > 0]
    if not rows:
        return None
    tot = sum(w for w, _ in rows)
    if tot <= 0:
        return None
    return _clamp(sum(w * p for w, p in rows) / tot, 0.0, 1.0)


def compose_binary(parsed: dict) -> tuple[float, bool, str]:
    """Return (inside_blended_prob, witness_ok, note). Calibration is applied later."""
    prior = _clamp(parsed.get("base_rate", 0.5), 0.0, 1.0)

    # inside view: prefer explicit branch mixture; else independent routes; else prior
    branches = parsed.get("branches")
    if branches:
        inside = _branch_mixture(branches)
        how = "branch-mixture"
    else:
        paths = parsed.get("yes_paths") or []
        ps = [_clamp(p.get("p", 0) if isinstance(p, dict) else p, 0, 1) for p in paths]
        blocker = _clamp(parsed.get("blocker_p", 0.0), 0.0, 1.0)
        inside = noisy_or(ps) * (1 - blocker) if ps else None
        how = "noisy-OR"
    if inside is None:
        inside = prior
        how = "prior-only"

    # prediction markets constrain, they do not anchor: floor/ceiling only
    fl = parsed.get("market_floor"); ce = parsed.get("market_ceiling")
    if isinstance(fl, (int, float)):
        inside = max(inside, _clamp(fl, 0, 1))
    if isinstance(ce, (int, float)):
        inside = min(inside, _clamp(ce, 0, 1))

    w = _clamp(parsed.get("inside_confidence", 0.5), 0.20, 0.85)
    raw = _clamp(w * inside + (1 - w) * prior, 0.0, 1.0)

    # witness: member's independently-stated P(YES) mass must match the computed inside view
    stated = parsed.get("mass_yes")
    witness_ok, note = True, f"inside={inside:.0%} via {how}; blended raw={raw:.0%}"
    if isinstance(stated, (int, float)):
        gap = abs(_clamp(stated, 0, 1) - inside)
        if gap > 0.25:
            witness_ok = False
            # distrust the structured number: pull hard toward the base rate
            raw = _clamp(0.35 * raw + 0.65 * prior, 0.0, 1.0)
            note += f"; WITNESS MISMATCH stated={stated:.0%} vs inside={inside:.0%} (gap {gap:.0%}) -> reverted toward prior={prior:.0%}, raw now {raw:.0%}"
    return raw, witness_ok, note
