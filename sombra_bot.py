"""sombra-bot — the Metaculus FutureEval bot.

Extends the Fall 2026 template with a structured forecasting brain. ALL the
Metaculus plumbing (question pulling, 5x-median ensemble, CDF building,
submission, the required reasoning comment, GitHub Actions scheduling) stays in
the template's ForecastBot machinery. The ONLY thing we override is
`run_research`: instead of a single news summary, it returns a structured,
falsification-hardened dossier produced by the owner's actor / game-theory
model (strategic questions) or a base-rate model (measurement questions). The
template's `_run_forecast_on_{binary,multiple_choice,numeric,date}` then turn
that dossier into the calibrated prediction, unchanged.

Run exactly like the template:  python sombra_bot.py --mode tournament
"""
from __future__ import annotations

import asyncio
import logging

import dotenv

from main import FallTemplateBot2026, logger  # template = validated plumbing
from forecasting_tools import MetaculusQuestion

from brain import analysis

logging.basicConfig(level=logging.INFO)


class SombraBot(FallTemplateBot2026):
    async def run_research(self, question: MetaculusQuestion) -> str:
        async with self._concurrency_limiter:
            # Reuse the template's news retrieval (AskNews/SmartSearcher) so we
            # inherit dated, real sources — fixing sombra's snippet-only weakness.
            news = await super().run_research(question)
            dossier = await analysis.build_dossier(self, question, news)
            logger.info(f"sombra dossier for {question.page_url}:\n{dossier}")
            return dossier


if __name__ == "__main__":
    import argparse

    dotenv.load_dotenv()
    parser = argparse.ArgumentParser(description="Run sombra-bot")
    parser.add_argument(
        "--mode",
        choices=["tournament", "test_questions"],
        default="tournament",
        help="tournament = live Fall-2026 + MiniBench; test_questions = bot-testing-area",
    )
    mode = parser.parse_args().mode

    from forecasting_tools import MetaculusClient

    bot = SombraBot(
        research_reports_per_question=1,
        predictions_per_research_report=5,  # template's 5x ensemble -> median
        publish_reports_to_metaculus=True,
        skip_previously_forecasted_questions=(mode == "tournament"),
    )
    client = MetaculusClient()

    if mode == "tournament":
        reports = asyncio.run(
            bot.forecast_on_tournament(client.CURRENT_AI_COMPETITION_ID, return_exceptions=True)
        )
        reports += asyncio.run(
            bot.forecast_on_tournament(client.CURRENT_MINIBENCH_ID, return_exceptions=True)
        )
    else:  # test_questions -> bot-testing-area
        reports = asyncio.run(
            bot.forecast_on_tournament("bot-testing-area", return_exceptions=True)
        )
    ok = [r for r in reports if not isinstance(r, Exception)]
    logger.info(f"sombra-bot done: {len(ok)}/{len(reports)} questions forecast "
                f"({len(reports) - len(ok)} errored).")
    try:
        FallTemplateBot2026.log_report_summary(reports)  # pretty summary if available
    except Exception:
        pass
