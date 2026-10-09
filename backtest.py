"""Offline backtest for sombra-bot (improvement #5, backtest half).

Runs the SAME brain over already-resolved HISTORICAL questions, pretending to
forecast as-of a past date, and scores it with brain/scoring.py. This is how we
answer the methodology-risk question honestly: does the actor/game-theory lens
actually EARN its place (beat the median, beat the crowd), or is it correlated
overconfidence? Do NOT trust the design until this says so.

Two entry points:
  python backtest.py run   --source metaculus --count 40 --out runs/bt.jsonl
  python backtest.py run   --source jsonl --in questions.jsonl --out runs/bt.jsonl
  python backtest.py score --in runs/bt.jsonl         # pure, no API key needed

`run` executes the full LLM pipeline → needs OPENROUTER_API_KEY (and, for
--source metaculus, a working MetaculusClient resolved-question query).
`score` only reads a records file and computes metrics → runs anywhere.

HONEST FIDELITY LIMIT: a true backtest also needs the RESEARCH to be as-of the
forecast date. We set `bot._asof_cutoff` so brain.hygiene.drop_sources_after
drops explicitly-dated sources published after the cutoff — but undated snippets
from a live news search can still leak. Treat scores as an upper bound on skill
until the research fetch itself is date-pinned. This limitation is the whole
reason the #14 leakage filter exists; tightening it is future work.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from datetime import date, datetime

from brain import scoring

_METHOD_RE = re.compile(r"AGGREGATION:\s*(.+)")


def extract_method(reasoning: str) -> str:
    m = _METHOD_RE.search(reasoning or "")
    return (m.group(1).strip() if m else "?")[:60]


class _ShimQuestion:
    """Duck-typed stand-in carrying exactly the attributes the brain reads, so a
    local fixture can drive the pipeline without the Metaculus types."""
    def __init__(self, d: dict):
        self.question_text = d.get("question_text", "")
        self.resolution_criteria = d.get("resolution_criteria", "")
        self.fine_print = d.get("fine_print", "")
        self.background_info = d.get("background_info", "")
        self.options = d.get("options", [])
        self.page_url = d.get("page_url", d.get("id", "local"))
        self.scheduled_resolution_time = d.get("resolution_date")
        self.scheduled_close_time = d.get("resolution_date")
        # ground truth + crowd for scoring (not read by the brain)
        self._outcome = d.get("outcome")
        self._community = d.get("community")
        self._asof = d.get("asof") or d.get("open_date")


def _asof_date(q) -> date | None:
    val = getattr(q, "_asof", None)
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00")).date()
        except ValueError:
            return None
    return val.date() if hasattr(val, "date") else val


async def forecast_asof(bot, question) -> dict:
    """Run the full binary pipeline as-of the question's past date; return a
    record {prob, outcome, community, method}. Never raises — a failed question
    is recorded with prob=None so it is simply dropped from the metrics."""
    from brain import analysis
    prev = getattr(bot, "_asof_cutoff", None)
    bot._asof_cutoff = _asof_date(question)
    try:
        research = await bot.run_research(question)
        prob, reasoning = await analysis.run_ensemble_binary(bot, question, research)
        method = extract_method(reasoning)
    except Exception as e:  # noqa
        prob, method = None, f"ERROR: {type(e).__name__}"
    finally:
        bot._asof_cutoff = prev
    return {
        "id": getattr(question, "page_url", "?"),
        "prob": prob,
        "outcome": getattr(question, "_outcome", None),
        "community": getattr(question, "_community", None),
        "method": method,
    }


async def run_backtest(bot, questions) -> list[dict]:
    """Forecast every question concurrently (the bot's own concurrency limiter
    still throttles the underlying LLM calls)."""
    return await asyncio.gather(*(forecast_asof(bot, q) for q in questions))


def load_jsonl_questions(path: str) -> list:
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(_ShimQuestion(json.loads(line)))
    return out


def load_metaculus_resolved(count: int):
    """Pull recently-resolved BINARY questions from Metaculus.

    UNVERIFIED OFFLINE: the exact forecasting_tools / MetaculusClient call is not
    pinned here because the package can't run in the dev sandbox. When the key
    lands, wire this against the real API in ONE place (below) and validate, then
    delete this warning. Until then it raises with precise instructions rather
    than guessing an API that silently returns nothing.
    """
    raise RuntimeError(
        "load_metaculus_resolved is not wired yet. When OPENROUTER_API_KEY + a "
        "working MetaculusClient are available, implement it here: query resolved "
        "binary questions (status=resolved, type=binary), and for each build a "
        "dict with question_text, resolution_criteria, fine_print, background_info, "
        "resolution_date, open_date (as-of), outcome (0/1), community (crowd prob "
        "at the as-of date). Feed those through _ShimQuestion or the native type. "
        "For now use: python backtest.py run --source jsonl --in questions.jsonl"
    )


def score_file(path: str) -> dict:
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    overall = scoring.summarize_binary(records)
    by_method = scoring.summarize_by_method(records)
    return {"overall": overall, "by_method": by_method, "n_records": len(records)}


def _print_summary(res: dict) -> None:
    o = res["overall"]
    print(f"\n=== BACKTEST ({res['n_records']} records, {o.get('n', 0)} scorable) ===")
    if not o.get("n"):
        print("  no scorable records.")
        return
    print(f"  Brier (lower better):   {o['brier']:.4f}")
    print(f"  Baseline (higher better): {o['baseline']:+.1f}")
    print(f"  ECE (lower better):     {o['ece']:.4f}")
    if "edge_over_community" in o:
        print(f"  vs community baseline:  {o['community_baseline']:+.1f} "
              f"-> EDGE {o['edge_over_community']:+.1f} over {o['n_vs_community']} Qs")
    print("  --- by aggregation method (does a lens earn its place?) ---")
    for method, s in sorted(res["by_method"].items(),
                            key=lambda kv: kv[1].get("baseline", -1e9), reverse=True):
        if s.get("n"):
            print(f"    {method:<40} n={s['n']:<4} baseline {s['baseline']:+.1f} "
                  f"brier {s['brier']:.3f}")


def _main():
    ap = argparse.ArgumentParser(description="sombra-bot offline backtest")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the pipeline over resolved questions (needs key)")
    r.add_argument("--source", choices=["metaculus", "jsonl"], default="jsonl")
    r.add_argument("--in", dest="infile", help="questions JSONL (for --source jsonl)")
    r.add_argument("--count", type=int, default=40, help="(for --source metaculus)")
    r.add_argument("--out", required=True, help="where to write the records JSONL")

    s = sub.add_parser("score", help="score an existing records file (no key needed)")
    s.add_argument("--in", dest="infile", required=True)

    args = ap.parse_args()

    if args.cmd == "score":
        _print_summary(score_file(args.infile))
        return

    # run
    import dotenv
    dotenv.load_dotenv()
    from sombra_bot import SombraBot

    if args.source == "jsonl":
        if not args.infile:
            ap.error("--source jsonl needs --in")
        questions = load_jsonl_questions(args.infile)
    else:
        questions = load_metaculus_resolved(args.count)

    bot = SombraBot(
        research_reports_per_question=1,
        predictions_per_research_report=1,  # backtest: one pass per question
        publish_reports_to_metaculus=False,  # never publish a backtest forecast
        skip_previously_forecasted_questions=False,
    )
    records = asyncio.run(run_backtest(bot, questions))
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    _print_summary(score_file(args.out))


if __name__ == "__main__":
    _main()
