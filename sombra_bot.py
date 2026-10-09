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

from main import FallTemplateBot2026, logger, structure_output  # template = validated plumbing
from forecasting_tools import (
    MetaculusQuestion,
    ReasonedPrediction,
    BinaryQuestion,
    NumericQuestion,
    NumericDistribution,
    Percentile,
    MultipleChoiceQuestion,
    PredictedOptionList,
)

from brain import analysis

logging.basicConfig(level=logging.INFO)


class SombraBot(FallTemplateBot2026):
    async def _run_forecast_on_binary(
        self, question: BinaryQuestion, research: str
    ) -> ReasonedPrediction[float]:
        # Use the structured, computed estimate instead of the template's
        # single-prompt guess. The 5x ensemble (predictions_per_research_report)
        # still runs and medians these, so variance is handled upstream.
        prob, reasoning = await analysis.run_ensemble_binary(self, question, research)
        return ReasonedPrediction(prediction_value=prob, reasoning=reasoning)

    async def _run_forecast_on_numeric(
        self, question: NumericQuestion, research: str
    ) -> ReasonedPrediction[NumericDistribution]:
        # Structured numeric lane: each reasoning lens emits a mixture of named
        # distribution components (one per resolution route); code inverts the
        # blended CDF into percentiles. If it yields nothing usable, fall back to
        # the template's validated single-prompt path rather than ship garbage.
        try:
            pcts, reasoning = await analysis.run_ensemble_numeric(self, question, research)
        except Exception as e:
            logger.warning(f"numeric ensemble failed for {question.page_url}: {e}")
            pcts = {}
            reasoning = ""
        if not pcts or len(pcts) < 3:
            logger.info(f"numeric ensemble empty for {question.page_url}; using template path")
            return await super()._run_forecast_on_numeric(question, research)

        percentile_list = [
            Percentile(percentile=float(q), value=float(v))
            for q, v in sorted(pcts.items())
        ]
        prediction = NumericDistribution.from_question(percentile_list, question)
        logger.info(
            f"sombra numeric {question.page_url}: {prediction.declared_percentiles}"
        )
        return ReasonedPrediction(prediction_value=prediction, reasoning=reasoning)

    async def _run_forecast_on_multiple_choice(
        self, question: MultipleChoiceQuestion, research: str
    ) -> ReasonedPrediction[PredictedOptionList]:
        # Diverse-panel distribution over the options. The probabilities are
        # COMPUTED in code (median-per-option + renormalize); we hand the computed
        # final answer to the template's own validated parser so the returned
        # PredictedOptionList is typed exactly as the plumbing expects.
        try:
            probs, reasoning = await analysis.run_ensemble_multiple_choice(
                self, question, research)
        except Exception as e:
            logger.warning(f"MC ensemble failed for {question.page_url}: {e}")
            probs = {}
            reasoning = ""
        if not probs:
            logger.info(f"MC ensemble empty for {question.page_url}; using template path")
            return await super()._run_forecast_on_multiple_choice(question, research)

        final_block = "\n".join(f"{opt}: {p * 100:.1f}%" for opt, p in probs.items())
        text = f"{reasoning}\n\nFinal probabilities:\n{final_block}"
        parsing_instructions = (
            f"Make sure every option name is one of: {question.options}. "
            "Do not skip any option; include 0% entries explicitly. Parse the "
            "probabilities verbatim from the 'Final probabilities' block."
        )
        predicted: PredictedOptionList = await structure_output(
            text_to_structure=text,
            output_type=PredictedOptionList,
            model=self.get_llm("parser", "llm"),
            num_validation_samples=self._structure_output_validation_samples,
            additional_instructions=parsing_instructions,
        )
        logger.info(f"sombra MC {question.page_url}: {predicted}")
        return ReasonedPrediction(prediction_value=predicted, reasoning=reasoning)

    async def research_query(self, query: str) -> str:
        """Run ONE arbitrary query through whatever researcher is configured —
        mirrors the template's run_research dispatch so the falsification loop
        gets fresh, dated sources rather than snippets."""
        researcher = self.get_llm("researcher")
        try:
            if isinstance(researcher, str) and researcher.startswith("asknews"):
                from forecasting_tools import AskNewsSearcher
                return await AskNewsSearcher().call_preconfigured_version(researcher, query)
            if isinstance(researcher, str) and researcher.startswith("smart-searcher"):
                from forecasting_tools import SmartSearcher
                model_name = researcher.removeprefix("smart-searcher/")
                return await SmartSearcher(model=model_name, temperature=0,
                                           num_searches_to_run=2, num_sites_per_search=6).invoke(query)
            if not researcher or researcher in ("None", "no_research"):
                return ""
            return await self.get_llm("researcher", "llm").invoke(query)
        except Exception as e:  # never let a failed re-search kill the forecast
            logger.warning(f"research_query failed for {query!r}: {e}")
            return ""

    async def run_research(self, question: MetaculusQuestion) -> str:
        async with self._concurrency_limiter:
            # Return the shared RAW research bundle. Every ensemble lens consumes
            # it; the actor member builds its structured dossier from it inside
            # the ensemble, so the dossier is NOT built here (built once, per
            # question, by the actor member).
            news = await super().run_research(question)
            logger.info(f"sombra research for {question.page_url}:\n{news[:500]}")
            return news


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
