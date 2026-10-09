# sombra-bot — improvement backlog

> **Coherence pass (2026-10-09).** The raw 24 would be a Frankenstein: three rival
> "compute the number" mechanisms, items needing data/track-record we don't have,
> and heavy subsystems. Pruned to ONE spine:
>
> **Research (shared bundle) → diverse ENSEMBLE of reasoning lenses → each composes
> a probability IN CODE with a self-check witness → median / tiebreaker-judge →
> calibrate → offline eval.** The methodology-naivety fix IS this spine: the
> actor/HM/game-theory brain is the strongest lens, never the only one.
>
> Status tags below: [done] [partial] [next] [deferred] [dropped].
>
> - [dropped] #10 Monte-Carlo-in-code — redundant 3rd composition path + sandbox risk; branch-mixture covers it.
> - [deferred] #7 full hidden-data-file ladder — ship simpler width-from-series first.
> - [deferred] #5 learned Platt fit — no resolved questions yet; keep heuristic calibration, build eval harness first.
> - [deferred] #13 full provider fanout (OpenAI/Gemini/FRED/yfinance/4 markets) — use AskNews + resolution-source + web; add incrementally.
> - [deferred] #15 fact/opinion split, #24 prompt caching — low priority.


Distilled from studying the top open-source FutureEval bots (Summer 2026):
nostreambot (#14), Panshul42 (#23, Q2'25 winner), Pirohuni (#24). Each item is
tagged with the bot(s) it came from. Ordered P1 (highest leverage) → P3.

## P1 — biggest leverage, fixes a known weakness

1. **[done] Diverse ensemble by reasoning PATH (actor + outside-view + market/status-quo); by model lineage once the key lands.** [all three]
   The strongest cross-bot lesson: shared briefings / same lineage → correlated
   errors. Our current 5x-same-model-on-one-dossier is exactly that trap. Make
   members differ: (a) the actor/game-theory brain as one member; (b) a plain
   base-rate / reference-class member on a *different* model lineage; optionally
   (c) a second-lens member (see methodology note). Blend by median.
2. **[done] Tiebreaker-judge on spread ≥ 30pp, not blind averaging.** [Pirohuni]
   If member spread ≥ ~30pp, a strong judge model re-reads the rationales and
   synthesizes one probability instead of medianing a bimodal split.
3. **[done] Answer-space witness: member states mass_yes; code reverts toward prior on mismatch.** [Pirohuni]
   The brain emits a unit-free statement of where its probability mass sits (and
   per-route probabilities); code checks the composed noisy-OR number matches,
   and auto-reverts / flags on divergence. Turns "computed, not guessed" into a
   self-checking invariant.
4. **[partial] Base rate as layer-0 + ingredient; sealed-pass-1 justification still soft.** [Panshul]
   Compute and freeze the reference-class prior first; the actor/game-theory
   update runs as pass-2 and must justify how far it moves off the sealed prior
   via a strong/moderate/weak evidence rubric. (We have layer 0; make it a gate.)
5. **[deferred] Learned calibration + offline eval loop (need resolutions first; heuristic horizon-calibration live now).** [nostream Platt; Panshul sim]
   Platt/isotonic fit on resolved questions, AND an expected-peer-score
   simulation to A/B configurations against the community prediction WITHOUT
   waiting for resolutions. Panshul decayed #1→#23 plausibly for lack of this.

## P2 — accuracy, especially the numeric lane we don't have natively

6. **[partial] Numeric = mixture of named components — MATH done & unit-tested (brain/numeric.py); forecast override not yet wired.** [Pirohuni]
   One component (normal/lognormal/…) per genuinely distinct resolution
   scenario — which maps 1:1 onto our game-theoretic routes/equilibria. Harness
   blends; LLM never emits raw percentiles.
7. **Empirical width from the resolution series.** [Pirohuni]
   series_discovery-style ladder to fetch the hidden data file (meta-refresh/JS
   redirect/iframe/bundle endpoints) for free, then size the 90% interval from
   how much the series ACTUALLY moved at the question's horizon. Biggest density
   win in their logs; no LLM reproduces it from rows.
8. **[partial] Monotone CDF (pure-Python) + quantile-space averaging done; tail widening next.** [all]
   Build a 201-pt monotone CDF (min/max-step rules, tail pinning); average CDFs
   in quantile space to preserve per-route spread; widen tails.
9. **[done] Markets as floor/ceiling + branch-mixture P(YES)=Σ w·p; full event-chain typing next.** [Pirohuni Phase 0.5]
   Classify related events upstream/same/downstream; fold prediction-market
   prices in as FLOORS/CEILINGS by entailment (never raw anchors); explicit
   branch-mixture arithmetic P(YES)=Σ P(branch)·P(YES|branch).
10. **Monte-Carlo-in-code lane.** [Panshul]
    For composable questions, emit the routes + dependencies as a small sim
    spec, generate NumPy, and RUN it (sandbox) — the most auditable form of
    "compute the number".

## P2 — research depth (fixes our AskNews-only / snippet weakness)

11. **Read the resolution source.** [nostream/Pirohuni] Fetch and read every URL
    the question names in its criteria/fine-print.
12. **Evidence-plan + artifact-check gap loop.** [Pirohuni] Name the single value
    the question resolves on BEFORE searching; after searching, verdict
    found/partial/missing and run one focused retry.
13. **Multi-source parallel research + 2 gap-fill passes.** [nostream] Add OpenAI
    native + Gemini grounded search alongside AskNews; two gap-fill rounds.
14. **Date-before leakage filter on all retrieval.** [Panshul] Drop sources
    published after the resolution date — also makes any future backtest honest.
15. **Per-article fact / named-opinion / unnamed-opinion split.** [Panshul]
16. **Filter once up front; shared selected evidence to all stages.** [Pirohuni]
17. **[partial] Falsification loop exists (multi-round, fresh search); two-sided + blind-spot targeting next.** [ours + Panshul] Two-sided (seek the
    strongest confirming AND disconfirming evidence), judge outputs a probability
    delta, queries tool-routed, and explicitly target the methodology's blind
    spots (non-material motives, institutional/accidental paths).

## P3 — robustness & engineering hygiene

18. **Time budget per question** (fast/slow path; skip if unpublishable before close). [nostream/Pirohuni]
19. **Token reserve** so research can't starve the reasoning/forecast tail. [Pirohuni]
20. **Deterministic authoritative banners** the LLM cannot override (e.g.
    "evidence MISSING") — critical so the falsification loop can't talk itself
    out of a real gap. [Pirohuni]
21. **Graceful degradation / abstain** rather than submit a broken forecast. [all]
22. **Structured-output repair/salvage** parsing before dropping a member. [nostream]
23. **INCIDENTS.md + golden-replay regression tests** keyed to question ids — our
    multi-stage pipeline has many serialization seams. [Pirohuni]
24. **Multi-model via OpenRouter + prompt caching** of the shared persona/system
    context for cost. [Panshul]

## Explicitly NOT doing
- A learned stacker / meta-combiner: all three tested it; none beat median. Keep
  median (+ the tiebreaker in #2).

## Methodology risk (see chat 2026-10-09)
The dialectical-HM + game-theory brain is our differentiator but is ONE lens →
systematic, correlated blind spots + inside-view overconfidence. Mitigation is
items #1 (diverse paths), #4 (sealed base rate), #9 (market floors/ceilings),
#17 (falsification targets the lens's blind spots), and #5 (measure whether the
lens actually adds value, don't assume).
