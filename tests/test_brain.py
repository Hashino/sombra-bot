"""Golden-replay regression tests for sombra-bot's deterministic cores
(improvement #23).

Our pipeline has many serialization seams — LLM text → parsed ingredients →
composed number → CDF → percentiles → submission object. These tests pin the
PURE, API-free math at every seam so a refactor can't silently change a forecast.
Run with `python3 -m pytest tests/` or directly `python3 tests/test_brain.py`.

When a real forecast goes wrong in production, record it in INCIDENTS.md and add
the reproducing case here (keyed by Metaculus question id) so it can't regress.
"""
import math
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain import estimate as E
from brain import compose as C
from brain import aggregate as A
from brain import numeric as N
from brain import hygiene as H
from brain import router as R


# --------------------------- estimate.py ----------------------------------- #

def test_noisy_or():
    assert E.noisy_or([]) == 0.0
    assert abs(E.noisy_or([0.5, 0.5]) - 0.75) < 1e-9
    assert E.noisy_or([1.0]) == 1.0


def test_compose_blends_toward_prior():
    # low inside confidence stays near prior
    p = E.compose(0.2, [0.9], 0.0, 0.20)
    assert 0.2 <= p <= 0.5


def test_calibrate_pulls_to_half_and_clamps():
    # longer horizon pulls harder toward 0.5
    near = E.calibrate(0.95, 1)
    far = E.calibrate(0.95, 180)
    assert near > far
    assert 0.02 <= E.calibrate(1.0, None) <= 0.98


def test_parse_estimate_salvage():
    assert E.parse_estimate('{"a":1}')["a"] == 1
    assert E.parse_estimate('```json\n{"a":1}\n```')["a"] == 1
    assert E.parse_estimate('{"a":1, "b":2,}')["b"] == 2          # trailing comma
    assert E.parse_estimate("{'a': 1}")["a"] == 1                  # single quotes
    assert E.parse_estimate('prefix {"a":1} suffix')["a"] == 1     # surrounding prose
    assert E.parse_estimate('{"note":"has {brace}","a":2}')["a"] == 2
    assert E.parse_estimate('{"a":1, "b":') is None               # truncated
    assert E.parse_estimate("no json") is None
    assert E.parse_estimate("") is None


# --------------------------- compose.py ------------------------------------ #

def test_branch_mixture():
    parsed = {"base_rate": 0.3, "inside_confidence": 0.85,
              "branches": [{"w": 0.6, "p_yes": 0.9}, {"w": 0.4, "p_yes": 0.1}]}
    raw, ok, note = C.compose_binary(parsed)
    assert ok and 0.0 <= raw <= 1.0 and "branch-mixture" in note


def test_market_floor_ceiling():
    parsed = {"base_rate": 0.5, "inside_confidence": 0.85,
              "branches": [{"w": 1, "p_yes": 0.1}], "market_floor": 0.4}
    raw, ok, note = C.compose_binary(parsed)
    assert raw >= 0.4 * 0.85  # floor lifts the inside view before blending


def test_witness_reverts_on_mismatch():
    parsed = {"base_rate": 0.2, "inside_confidence": 0.85,
              "branches": [{"w": 1, "p_yes": 0.95}], "mass_yes": 0.1}
    raw, ok, note = C.compose_binary(parsed)
    assert not ok and "WITNESS MISMATCH" in note and raw < 0.6


# --------------------------- aggregate.py ---------------------------------- #

def test_aggregate_binary_tiebreaker():
    assert A.aggregate_binary([0.2, 0.25, 0.8])["needs_tiebreaker"]
    assert not A.aggregate_binary([0.4, 0.45, 0.5])["needs_tiebreaker"]
    assert abs(A.aggregate_binary([0.2, 0.4, 0.6])["prob"] - 0.4) < 1e-9


def test_aggregate_mc_normalizes_and_floors():
    opts = ["A", "B", "C"]
    agg = A.aggregate_multiple_choice(
        [{"A": 0.6, "B": 0.3, "C": 0.1}, {"A": 0.1, "B": 0.1, "C": 0.8}], opts)
    assert abs(sum(agg["probs"].values()) - 1.0) < 1e-9
    assert all(v > 0 for v in agg["probs"].values())


def test_normalize_option_probs():
    opts = ["A", "B", "C"]
    n = A.normalize_option_probs({"A": 2, "B": 2, "Z": 9}, opts)
    assert abs(sum(n.values()) - 1) < 1e-9 and n["C"] == 0.0
    z = A.normalize_option_probs({}, opts)
    assert all(abs(v - 1 / 3) < 1e-9 for v in z.values())


# --------------------------- numeric.py ------------------------------------ #

def test_mixture_cdf_monotone_and_bounds():
    comps = [{"family": "normal", "mean": 10, "sd": 2, "w": 0.6},
             {"family": "normal", "mean": 40, "sd": 3, "w": 0.4}]
    assert N.mixture_cdf(comps, -1e6) < 1e-6
    assert N.mixture_cdf(comps, 1e6) > 1 - 1e-6
    lo, hi = N.component_search_range(comps)
    pct = N.percentiles_from_mixture(comps, lo, hi)
    xs = [pct[q] for q in sorted(pct)]
    assert all(a <= b + 1e-6 for a, b in zip(xs, xs[1:]))


def test_lognormal_median():
    ln = [{"family": "lognormal", "mu": 2.0, "sigma": 0.5, "w": 1}]
    pct = N.percentiles_from_mixture(ln, *N.component_search_range(ln))
    assert abs(pct[0.5] - math.exp(2)) < 0.5


def test_widen_and_clamp():
    comps = [{"family": "normal", "mean": 20, "sd": 5, "w": 1}]
    pct = N.percentiles_from_mixture(comps, 0, 40)
    w = N.widen_tails(pct, 1.2)
    assert w[0.05] <= pct[0.05] + 1e-9 and w[0.95] >= pct[0.95] - 1e-9
    assert abs(w[0.5] - pct[0.5]) < 1e-9
    c = N.clamp_to_bounds(w, 0.0, 30.0, open_lo=False, open_hi=True)
    assert min(c.values()) >= 0.0


# --------------------------- hygiene.py ------------------------------------ #

def test_evidence_state():
    assert H.evidence_state("")[0] == "missing"
    assert H.evidence_state("(no external research available)")[0] == "missing"
    assert H.evidence_state("x" * 50)[0] == "thin"
    assert H.evidence_state("y" * 300)[0] == "ok"
    assert "cannot be overridden" in H.evidence_state("")[1]


def test_date_leakage_filter():
    txt = ("A 2026-09-01 foo\n\nB 2026-12-20 bar\n\nUndated baz")
    out = H.drop_sources_after(txt, date(2026, 10, 9))
    assert "A 2026-09-01" in out and "Undated" in out and "2026-12-20" not in out
    assert H.drop_sources_after(txt, None) == txt            # no cutoff -> no-op
    assert "2026-12-20" not in H.drop_sources_after(txt, "2026-10-09")


# --------------------------- router.py ------------------------------------- #

def test_router_lanes():
    s = R.classify_text("Will the EU pass the sanctions bill by March?", "")
    assert s.lane == "strategic"
    m = R.classify_text("What will the CPI inflation rate be in Q3?", "")
    assert m.lane == "measurement"


# --------------------------- analysis.py (pure parts) ---------------------- #

def test_extract_urls_dedupes_and_strips():
    from brain import analysis as An

    class Q:
        resolution_criteria = "per https://ex.gov/r, see https://ex.gov/r (dupe)."
        fine_print = "also https://data.org/s.csv)."
        question_text = "Will X?"
        background_info = ""

    assert An._extract_urls(Q()) == ["https://ex.gov/r", "https://data.org/s.csv"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  ok  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {fn.__name__}: {e}")
        except Exception as e:  # noqa
            failed += 1
            print(f"ERR   {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
