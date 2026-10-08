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


async def estimate_binary(bot, question, dossier: str) -> tuple[float, str]:
    """Improvement #1+#2+#3: compose the probability from elicited ingredients
    (base rate + actor-path probabilities), then calibrate. Falls back to a
    plain single-number ask if the structured elicitation can't be parsed."""
    days = _days_to_resolution(question)
    raw = await _ask(
        bot,
        prompts.ESTIMATE_BINARY.format(
            q=getattr(question, "question_text", ""),
            rc=getattr(question, "resolution_criteria", "") or "",
            dossier=dossier,
        ),
    )
    parsed = estimate.parse_estimate(raw)
    if parsed and "base_rate" in parsed:
        prob, breakdown = estimate.estimate_probability(parsed, days)
        return prob, dossier + "\n\n" + breakdown

    # Fallback: never crash — ask for a bare probability the template way.
    import re
    ask = await _ask(
        bot,
        f"Based on this analysis, give ONLY the final probability the answer is "
        f"YES, as 'Probability: NN%'.\n\n{dossier}",
    )
    m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", ask or "")
    p = estimate._clamp((float(m.group(1)) / 100.0) if m else 0.5, 0.02, 0.98)
    p = estimate.calibrate(p, days)
    return p, dossier + f"\n\n(structured parse failed; calibrated fallback = {p:.1%})"
