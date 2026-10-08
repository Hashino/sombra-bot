"""Orchestration of the structured forecasting brain.

All LLM access goes through the bot's own `get_llm` (so model choice, retries
and rate-limits are the template's), which keeps this module free of any
forecasting_tools import and therefore unit-importable on its own.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import prompts
from . import router


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


async def _falsify(bot, question, dossier: str, news: str) -> str:
    """Single bounded adversarial pass (sombra's verify loop, retargeted from
    'is there a contradiction' to 'does the evidence move the READ'). v1 does one
    attack+revise round; multi-round with fresh web re-search is the next step."""
    q = getattr(question, "question_text", "")
    attack = await _ask(
        bot,
        prompts.FALSIFY_ATTACK.format(q=q, dossier=dossier,
                                      news=news or "(none)"),
    )
    revised = await _ask(
        bot,
        prompts.FALSIFY_REVISE.format(q=q, dossier=dossier, attack=attack),
    )
    return revised
