"""Numeric forecasting: a mixture of named smooth components (one per resolution
scenario / game-theoretic route), blended by code into percentiles. Maps 1:1
onto the actor model's branches. Pure stdlib (normal CDF via math.erf); families:
normal, lognormal, truncated_normal (others map onto these for v1).
Quantile-space averaging across ensemble members preserves per-route spread.
"""
from __future__ import annotations

import math

_SQRT2 = math.sqrt(2.0)


def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / _SQRT2))


def _component_cdf(c: dict, x: float) -> float:
    fam = (c.get("family") or "normal").lower()
    if fam in ("lognormal",):
        if x <= 0:
            return 0.0
        mu = float(c.get("mu", c.get("median_log", 0.0)))
        sigma = max(1e-9, float(c.get("sigma", 1.0)))
        return _phi((math.log(x) - mu) / sigma)
    # normal / truncated_normal / fallback
    mean = float(c.get("mean", c.get("median", 0.0)))
    sd = max(1e-9, float(c.get("sd", c.get("std", 1.0))))
    cdf = _phi((x - mean) / sd)
    lo, hi = c.get("lo"), c.get("hi")
    if fam == "truncated_normal" and lo is not None and hi is not None:
        a = _phi((float(lo) - mean) / sd); b = _phi((float(hi) - mean) / sd)
        if b - a < 1e-9:
            return 0.0 if x < float(lo) else 1.0
        return min(1.0, max(0.0, (cdf - a) / (b - a)))
    return cdf


def mixture_cdf(components: list[dict], x: float) -> float:
    rows = [(max(0.0, float(c.get("w", 1.0))), c) for c in components]
    tot = sum(w for w, _ in rows) or 1.0
    return sum(w * _component_cdf(c, x) for w, c in rows) / tot


def percentiles_from_mixture(components: list[dict], lo: float, hi: float,
                             qs=(0.05, 0.1, 0.2, 0.4, 0.5, 0.6, 0.8, 0.9, 0.95)) -> dict:
    """Invert the mixture CDF by bisection on [lo, hi]. Returns {q: x}."""
    if hi <= lo:
        hi = lo + 1.0
    out = {}
    for q in qs:
        a, b = lo, hi
        for _ in range(60):
            m = 0.5 * (a + b)
            if mixture_cdf(components, m) < q:
                a = m
            else:
                b = m
        out[q] = 0.5 * (a + b)
    return out


def quantile_space_average(percentile_dicts: list[dict]) -> dict:
    """Average member distributions in quantile space (preserves spread)."""
    if not percentile_dicts:
        return {}
    qs = sorted(set().union(*[set(d) for d in percentile_dicts]))
    out = {}
    for q in qs:
        vals = [d[q] for d in percentile_dicts if q in d]
        out[q] = sum(vals) / len(vals)
    # enforce monotonic non-decreasing in value
    last = None
    for q in qs:
        if last is not None and out[q] < last:
            out[q] = last
        last = out[q]
    return out


def component_search_range(components: list[dict], pad_sd: float = 4.0) -> tuple[float, float]:
    """Derive a [lo, hi] bracket to invert the CDF over, from the components
    themselves — used when the question's bound is OPEN (no hard limit)."""
    los, his = [], []
    for c in components:
        fam = (c.get("family") or "normal").lower()
        if fam == "lognormal":
            mu = float(c.get("mu", c.get("median_log", 0.0)))
            sigma = max(1e-9, float(c.get("sigma", 1.0)))
            los.append(math.exp(mu - pad_sd * sigma))
            his.append(math.exp(mu + pad_sd * sigma))
        else:
            mean = float(c.get("mean", c.get("median", 0.0)))
            sd = max(1e-9, float(c.get("sd", c.get("std", 1.0))))
            los.append(mean - pad_sd * sd)
            his.append(mean + pad_sd * sd)
    if not los:
        return (0.0, 1.0)
    return (min(los), max(his))


def widen_tails(pcts: dict, factor: float = 1.15) -> dict:
    """Push the outer percentiles further from the median (humility about unknown
    unknowns — every studied bot widened and never narrowed). Interior untouched."""
    if not pcts:
        return pcts
    qs = sorted(pcts)
    mid = pcts.get(0.5) or pcts[qs[len(qs) // 2]]
    out = {}
    for q in qs:
        if q <= 0.1 or q >= 0.9:
            out[q] = mid + factor * (pcts[q] - mid)
        else:
            out[q] = pcts[q]
    # re-impose monotonicity after widening
    last = None
    for q in qs:
        if last is not None and out[q] < last:
            out[q] = last
        last = out[q]
    return out


def clamp_to_bounds(pcts: dict, lo, hi, open_lo: bool, open_hi: bool) -> dict:
    """Clamp percentile VALUES into the question's declared bounds. A CLOSED bound
    is a hard wall; an OPEN bound is only a soft hint, so we leave a little room
    past it rather than pinning mass onto the wall."""
    if not pcts:
        return pcts
    out = dict(pcts)
    span = (max(pcts.values()) - min(pcts.values())) or 1.0
    if lo is not None:
        wall = float(lo) if not open_lo else float(lo) - 0.10 * span
        out = {q: max(v, wall) for q, v in out.items()}
    if hi is not None:
        wall = float(hi) if not open_hi else float(hi) + 0.10 * span
        out = {q: min(v, wall) for q, v in out.items()}
    # monotonicity again (clamping two walls can invert near-degenerate cases)
    qs = sorted(out)
    last = None
    for q in qs:
        if last is not None and out[q] < last:
            out[q] = last
        last = out[q]
    return out
