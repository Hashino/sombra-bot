"""Orchestration of the structured forecasting brain.

All LLM access goes through the bot's own `get_llm` (so model choice, retries
and rate-limits are the template's), which keeps this module free of any
forecasting_tools import and therefore unit-importable on its own.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from . import prompts
from . import router
from . import estimate
from . import hygiene


def _resolution_date(question):
    """A date object for the question's resolution/close, for the leakage filter."""
    from datetime import datetime, timezone
    for attr in ("scheduled_resolution_time", "actual_resolve_time",
                 "scheduled_close_time", "actual_close_time", "close_time"):
        val = getattr(question, attr, None)
        if not val:
            continue
        try:
            if isinstance(val, str):
                val = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return val.date() if hasattr(val, "date") else None
        except Exception:
            continue
    return None


def _prepare_research(question, research: str) -> tuple[str, str]:
    """Deterministic pre-pass shared by every lane: drop post-cutoff sources
    (#14) and stamp an authoritative evidence banner (#20). Returns
    (research_for_llm, evidence_level)."""
    clean = hygiene.drop_sources_after(research or "", _resolution_date(question))
    level, banner = hygiene.evidence_state(clean)
    out = (banner + "\n\n" + clean) if banner else clean
    return out, level


async def _ask(bot, prompt: str, role: str = "default") -> str:
    return await bot.get_llm(role, "llm").invoke(prompt)


async def route(bot, question, heuristic: router.Routing | None = None) -> str:
    """Return the lane. Trust a confident heuristic; otherwise let the LLM break the tie."""
    h = heuristic or router.classify(question)
    if h.confidence >= 0.45:
        return h.lane
    ans = await _ask(
        bot,
        prompts.ROUTE.format(
            q=getattr(question, "question_text", ""),
            rc=getattr(question, "resolution_criteria", "") or "",
        ),
    )
    ans = (ans or "").strip().lower()
    if "measurement" in ans:
        return "measurement"
    if "strategic" in ans:
        return "strategic"
    return h.lane  # fall back to the heuristic's best guess


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def build_dossier(bot, question, news: str) -> str:
    """Route, run the matching structured analysis, then falsify-and-refine."""
    lane = await route(bot, question)
    common = dict(
        q=getattr(question, "question_text", ""),
        rc=getattr(question, "resolution_criteria", "") or "",
        fp=getattr(question, "fine_print", "") or "",
        today=_today(),
        news=news or "(no external research available)",
    )
    tmpl = prompts.STRATEGIC if lane == "strategic" else prompts.MEASUREMENT
    dossier = await _ask(bot, tmpl.format(**common))
    dossier = await _falsify(bot, question, dossier, news)
    header = f"[sombra-bot lane: {lane}]\n"
    return header + dossier


async def _falsify(bot, question, dossier: str, news: str, max_rounds: int = 2) -> str:
    """Bounded, multi-round adversarial loop (sombra's verify.py, retargeted).

    Each round: generate queries that try to DISPROVE the READ -> run them as
    FRESH web searches -> judge whether the new evidence moves the READ -> if
    yes, revise and go again; if no, stop early. Searching anew each round is
    the point: it surfaces disconfirming evidence the first pass never looked for.
    """
    q = getattr(question, "question_text", "")
    for _ in range(max_rounds):
        raw = await _ask(bot, prompts.FALSIFY_QUERIES.format(q=q, dossier=dossier))
        queries = [ln.strip(" -\t") for ln in (raw or "").splitlines() if ln.strip()]
        queries = [x for x in queries if x.upper() != "NONE"][:4]
        if not queries:
            break
        # fresh searches, concurrently (sombra's search_agent shape)
        found = await asyncio.gather(
            *(bot.research_query(x) for x in queries), return_exceptions=True
        )
        evidence = "\n\n".join(
            f"Q: {qq}\n{ev}" for qq, ev in zip(queries, found)
            if not isinstance(ev, Exception) and ev
        )
        if not evidence.strip():
            break
        verdict = await _ask(
            bot, prompts.FALSIFY_JUDGE.format(q=q, dossier=dossier, evidence=evidence)
        )
        if "MOVES: YES" not in (verdict or "").upper():
            break  # evidence does not move the READ -> stop early
        dossier = await _ask(
            bot,
            prompts.FALSIFY_REVISE.format(
                q=q, dossier=dossier,
                attack=f"{verdict}\n\nEvidence:\n{evidence}",
            ),
        )
    return dossier


def _days_to_resolution(question) -> float | None:
    """Best-effort days from now to the question's resolution/close date."""
    from datetime import datetime, timezone
    for attr in ("scheduled_resolution_time", "actual_resolve_time",
                 "scheduled_close_time", "actual_close_time", "close_time"):
        val = getattr(question, attr, None)
        if not val:
            continue
        try:
            if isinstance(val, str):
                val = datetime.fromisoformat(val.replace("Z", "+00:00"))
            if val.tzinfo is None:
                val = val.replace(tzinfo=timezone.utc)
            return (val - datetime.now(timezone.utc)).total_seconds() / 86400.0
        except Exception:
            continue
    return None


async def _member_estimate(bot, question, lens: str, context: str):
    """Run one lens, parse its ingredients, compose a probability + witness."""
    from . import compose, estimate as E
    tmpl = {"actor": prompts.ESTIMATE_BINARY, "outside": prompts.OUTSIDE_BINARY,
            "market": prompts.MARKET_BINARY}[lens]
    key = "dossier" if lens == "actor" else "research"
    raw = await _ask(bot, tmpl.format(q=getattr(question,"question_text",""),
                                      rc=getattr(question,"resolution_criteria","") or "",
                                      **{key: context}))
    parsed = E.parse_estimate(raw)
    if not parsed or "base_rate" not in parsed:
        return None
    p, ok, note = compose.compose_binary(parsed)
    return {"lens": lens, "prob": p, "witness_ok": ok, "note": note}


async def run_ensemble_binary(bot, question, research: str) -> tuple[float, str]:
    """Improvement #1 (THE anti-naivety fix): forecast with a DIVERSE PANEL of
    reasoning lenses, not one. (actor/game-theory brain) + (pure outside-view
    base rate) + (market/status-quo). Median; a wide split triggers a judge
    synthesis instead of blind averaging; then calibrate by horizon."""
    import asyncio
    from . import aggregate, estimate as E

    research, ev_level = _prepare_research(question, research)
    # the actor member gets the full falsification-hardened dossier; the other
    # two are lighter, deliberately decorrelated reasoning paths.
    actor_dossier = await build_dossier(bot, question, research)
    members = await asyncio.gather(
        _member_estimate(bot, question, "actor", actor_dossier),
        _member_estimate(bot, question, "outside", research),
        _member_estimate(bot, question, "market", research),
    )
    members = [m for m in members if m]
    if not members:
        # total failure -> fall back to a single plain estimate
        return await _fallback_binary(bot, question, actor_dossier)

    agg = aggregate.aggregate_binary([m["prob"] for m in members])
    days = _days_to_resolution(question)

    if agg["needs_tiebreaker"]:
        import re
        body = "\n".join(f"- {m['lens']}: P(YES)={m['prob']:.0%} ({m['note']})" for m in members)
        judged = await _ask(bot, prompts.JUDGE_BINARY.format(
            q=getattr(question,"question_text",""), members=body))
        mm = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", judged or "")
        final = E._clamp((float(mm.group(1))/100.0) if mm else agg["prob"], 0.0, 1.0)
        method = f"tiebreaker-judge (spread {agg['spread']:.0%})"
    else:
        final = agg["prob"]
        method = f"median of {agg['n']} lenses (spread {agg['spread']:.0%})"

    final = E.calibrate(final, days)
    reasoning = (actor_dossier + "\n\nPANEL:\n"
                 + "\n".join(f"- {m['lens']}: {m['prob']:.0%}"
                              + ("" if m["witness_ok"] else " [witness reverted]")
                              + f" — {m['note']}" for m in members)
                 + f"\n\nEVIDENCE: {ev_level}"
                 + f"\nAGGREGATION: {method} -> calibrated {final:.1%}")
    return final, reasoning


async def _fallback_binary(bot, question, dossier: str) -> tuple[float, str]:
    import re
    from . import estimate as E
    ask = await _ask(bot, f"Give ONLY 'Probability: NN%' for YES.\n\n{dossier}")
    m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", ask or "")
    p = E.calibrate(E._clamp((float(m.group(1))/100.0) if m else 0.5, 0.02, 0.98),
                    _days_to_resolution(question))
    return p, dossier + f"\n\n(ensemble failed; fallback {p:.1%})"


async def estimate_binary(bot, question, dossier: str) -> tuple[float, str]:
    # kept for compatibility; delegates to the ensemble (research == dossier context)
    return await run_ensemble_binary(bot, question, dossier)


# --------------------------------------------------------------------------- #
#  Numeric / date lane (improvement #6/#8): mixture of named components per    #
#  resolution route -> monotone CDF -> quantile-space average across lenses.   #
# --------------------------------------------------------------------------- #

def _numeric_bounds(question):
    """(lo, hi, open_lo, open_hi, unit) from the question, nominal bounds first.
    None for a bound means "no usable hard limit" (treat as open)."""
    def _num(*names):
        for n in names:
            v = getattr(question, n, None)
            if v is not None:
                return v
        return None
    lo = _num("nominal_lower_bound", "lower_bound")
    hi = _num("nominal_upper_bound", "upper_bound")
    open_lo = bool(getattr(question, "open_lower_bound", False))
    open_hi = bool(getattr(question, "open_upper_bound", False))
    unit = getattr(question, "unit_of_measure", None) or "(infer the unit)"
    # dates arrive as datetimes; the override converts, so keep numeric here only
    return lo, hi, open_lo, open_hi, unit


async def _numeric_member(bot, question, lens: str, context: str, unit: str):
    from . import estimate as E
    tmpl = {"structural": prompts.NUMERIC_STRUCTURAL,
            "outside": prompts.NUMERIC_OUTSIDE,
            "statusquo": prompts.NUMERIC_STATUSQUO}[lens]
    key = "dossier" if lens == "structural" else "research"
    raw = await _ask(bot, tmpl.format(
        q=getattr(question, "question_text", ""),
        rc=getattr(question, "resolution_criteria", "") or "",
        unit=unit, **{key: context}))
    parsed = E.parse_estimate(raw)
    comps = (parsed or {}).get("components") if parsed else None
    if not comps or not isinstance(comps, list):
        return None
    good = [c for c in comps if isinstance(c, dict)]
    if not good:
        return None
    return {"lens": lens, "components": good, "note": (parsed or {}).get("note", "")}


async def run_ensemble_numeric(bot, question, research: str) -> tuple[dict, str]:
    """Return ({q(0-1): value}, reasoning). The binary panel's logic, adapted:
    the structural member maps game-theoretic branches to distribution components;
    outside-view and status-quo decorrelate it; code blends in quantile space."""
    from . import numeric as N

    research, _ = _prepare_research(question, research)
    lo, hi, open_lo, open_hi, unit = _numeric_bounds(question)
    dossier = await build_dossier(bot, question, research)
    members = await asyncio.gather(
        _numeric_member(bot, question, "structural", dossier, unit),
        _numeric_member(bot, question, "outside", research, unit),
        _numeric_member(bot, question, "statusquo", research, unit),
    )
    members = [m for m in members if m]
    qs = (0.05, 0.1, 0.2, 0.4, 0.5, 0.6, 0.8, 0.9, 0.95)

    member_pcts = []
    for m in members:
        comps = m["components"]
        # bracket to invert over: hard bounds when closed, else component-derived
        c_lo, c_hi = N.component_search_range(comps)
        blo = float(lo) if (lo is not None and not open_lo) else c_lo
        bhi = float(hi) if (hi is not None and not open_hi) else c_hi
        if bhi <= blo:
            blo, bhi = c_lo, c_hi
        member_pcts.append(N.percentiles_from_mixture(comps, blo, bhi, qs))

    if not member_pcts:
        return {}, dossier + "\n\n(numeric ensemble produced no components)"

    blended = N.quantile_space_average(member_pcts)
    blended = N.widen_tails(blended)
    blended = N.clamp_to_bounds(blended, lo, hi, open_lo, open_hi)

    panel = "\n".join(
        f"- {m['lens']}: {len(m['components'])} component(s) — {m['note']}"
        for m in members)
    pct_line = ", ".join(f"P{int(q*100)}={blended[q]:.4g}" for q in sorted(blended))
    reasoning = (dossier + "\n\nNUMERIC PANEL (mixture of components per route):\n"
                 + panel + "\n\nBLENDED (quantile-space, tails widened, bounds applied):\n"
                 + pct_line)
    return blended, reasoning


# --------------------------------------------------------------------------- #
#  Multiple-choice lane (improvement #1 extended): same diverse panel, but the #
#  members emit a distribution over a fixed option set; code medians per-option#
#  and renormalizes (never a learned stacker).                                 #
# --------------------------------------------------------------------------- #

async def _mc_member(bot, question, lens: str, context: str, options: list):
    from . import estimate as E, aggregate as A
    tmpl = {"actor": prompts.ESTIMATE_MC, "outside": prompts.OUTSIDE_MC,
            "market": prompts.MARKET_MC}[lens]
    key = "dossier" if lens == "actor" else "research"
    raw = await _ask(bot, tmpl.format(
        q=getattr(question, "question_text", ""),
        rc=getattr(question, "resolution_criteria", "") or "",
        options=options, **{key: context}))
    parsed = E.parse_estimate(raw)
    if not parsed:
        return None
    probs = A.normalize_option_probs(parsed, options)
    return {"lens": lens, "probs": probs, "note": parsed.get("note", "")}


async def run_ensemble_multiple_choice(bot, question, research: str) -> tuple[dict, str]:
    """Return ({option: prob}, reasoning). Diverse panel -> per-option median ->
    floor + renormalize; a wide split triggers a judge synthesis."""
    from . import aggregate as A, estimate as E

    options = list(getattr(question, "options", []) or [])
    if not options:
        return {}, "(no options on question)"

    research, _ = _prepare_research(question, research)
    dossier = await build_dossier(bot, question, research)
    members = await asyncio.gather(
        _mc_member(bot, question, "actor", dossier, options),
        _mc_member(bot, question, "outside", research, options),
        _mc_member(bot, question, "market", research, options),
    )
    members = [m for m in members if m]
    if not members:
        return {}, dossier + "\n\n(MC ensemble produced no members)"

    agg = A.aggregate_multiple_choice([m["probs"] for m in members], options)
    probs, method = agg["probs"], f"per-option median of {agg['n']} lenses"

    if agg.get("needs_tiebreaker"):
        body = "\n".join(
            f"- {m['lens']}: " + ", ".join(f"{o}={m['probs'][o]:.0%}" for o in options)
            + f" ({m['note']})" for m in members)
        judged = await _ask(bot, prompts.JUDGE_MC.format(
            q=getattr(question, "question_text", ""), options=options, members=body))
        parsed = E.parse_estimate(judged)
        if parsed:
            probs = A.normalize_option_probs(parsed, options)
            method = f"tiebreaker-judge (spread {agg['spread']:.0%})"

    panel = "\n".join(
        f"- {m['lens']}: " + ", ".join(f"{o}={m['probs'][o]:.0%}" for o in options)
        for m in members)
    final = ", ".join(f"{o}={probs[o]:.1%}" for o in options)
    reasoning = (dossier + "\n\nMC PANEL:\n" + panel
                 + f"\n\nAGGREGATION: {method}\nFINAL: {final}")
    return probs, reasoning
