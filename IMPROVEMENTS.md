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
> **State as of 2026-10-09 (second pass).** The whole coherent spine is now built
> and unit-tested offline: binary + numeric + multiple-choice lanes, the diverse
> 3-lens panel with tiebreaker + answer-space witness, sealed base-rate gate,
> two-sided blind-spot falsification, research orchestration (evidence plan +
> resolution-source read + artifact-check gap loop), deterministic evidence
> banner + date-leakage filter, parser salvage, bounded time/token budget,
> graceful degradation on every lane, and a 17-case golden-replay suite +
> INCIDENTS.md. What remains is genuinely blocked, not skipped:
>
> - [dropped] #10 Monte-Carlo-in-code — redundant 3rd composition path + sandbox risk; branch-mixture covers it.
> - [blocked-on-resolutions] #5 learned Platt fit — no resolved questions yet; heuristic horizon-calibration live. Build the eval harness after the first MiniBench round resolves.
> - [blocked-on-key] #1b model-LINEAGE diversity, #13 provider fanout, #24 prompt caching — need OPENROUTER_API_KEY + provider config; the reasoning-PATH diversity (the load-bearing half of #1) is already live.
> - [deferred] #7 full hidden-data-file scraper ladder — the status-quo numeric lens already sizes width from the series; the 40-hop ladder is a later density tweak.
> - [deferred] #15 fact/opinion split — low marginal value over the current research pass.
> - [done] #16 filter-once / shared bundle — one _prepare_research pre-pass feeds the same cleaned+bannered bundle to every lens.


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
4. **[done] Sealed base-rate gate: P0 frozen in layer 0; the READ must justify its move off P0 via a strong/moderate/weak rubric; independent check = the outside-view lens.** [Panshul]
   Compute and freeze the reference-class prior first; the actor/game-theory
   update runs as pass-2 and must justify how far it moves off the sealed prior
   via a strong/moderate/weak evidence rubric. (We have layer 0; make it a gate.)
5. **[deferred] Learned calibration + offline eval loop (need resolutions first; heuristic horizon-calibration live now).** [nostream Platt; Panshul sim]
   Platt/isotonic fit on resolved questions, AND an expected-peer-score
   simulation to A/B configurations against the community prediction WITHOUT
   waiting for resolutions. Panshul decayed #1→#23 plausibly for lack of this.

## P2 — accuracy, especially the numeric lane we don't have natively

6. **[done] Numeric = mixture of named components, one per route; _run_forecast_on_numeric wired, falls back to template on failure.** [Pirohuni]
   One component (normal/lognormal/…) per genuinely distinct resolution
   scenario — which maps 1:1 onto our game-theoretic routes/equilibria. Harness
   blends; LLM never emits raw percentiles.
7. **Empirical width from the resolution series.** [Pirohuni]
   series_discovery-style ladder to fetch the hidden data file (meta-refresh/JS
   redirect/iframe/bundle endpoints) for free, then size the 90% interval from
   how much the series ACTUALLY moved at the question's horizon. Biggest density
   win in their logs; no LLM reproduces it from rows.
8. **[done] Monotone CDF (pure-Python) + quantile-space averaging + tail widening + bound clamping, all unit-tested.** [all]
   Build a 201-pt monotone CDF (min/max-step rules, tail pinning); average CDFs
   in quantile space to preserve per-route spread; widen tails.
9. **[done] Markets as floor/ceiling + branch-mixture P(YES)=Σ w·p. (Full upstream/downstream event-chain typing left as a later refinement.)** [Pirohuni Phase 0.5]
   Classify related events upstream/same/downstream; fold prediction-market
   prices in as FLOORS/CEILINGS by entailment (never raw anchors); explicit
   branch-mixture arithmetic P(YES)=Σ P(branch)·P(YES|branch).
10. **Monte-Carlo-in-code lane.** [Panshul]
    For composable questions, emit the routes + dependencies as a small sim
    spec, generate NumPy, and RUN it (sandbox) — the most auditable form of
    "compute the number".

## P2 — research depth (fixes our AskNews-only / snippet weakness)

11. **[done] Read the resolution source.** [nostream/Pirohuni] augment_research extracts every URL the question names and queries each for the resolving value.
12. **[done] Evidence-plan + artifact-check gap loop.** [Pirohuni] Name the resolving value before searching; verdict found/partial/missing; one focused retry.
13. **[blocked-on-key] Multi-source parallel research + gap-fill passes.** [nostream] The falsification loop already does fresh multi-round search; extra providers need the key + config.
14. **[done] Date-before leakage filter (hygiene.drop_sources_after).** [Panshul] No-op live; keeps backtests honest.
15. **[deferred] Per-article fact / named-opinion / unnamed-opinion split.** [Panshul]
16. **[done] Filter once up front; one shared cleaned+bannered bundle to all lenses (_prepare_research).** [Pirohuni]
17. **[done] Two-sided falsification targeting the lens's blind spots.** [ours + Panshul] Queries seek confirming AND disconfirming evidence and probe non-material motives / institutional / accidental paths; judge gates revision.

## P3 — robustness & engineering hygiene

18. **[done] Time budget: research augmentation is time-boxed and dropped on overrun so the reasoning tail always runs.** [nostream/Pirohuni]
19. **[partial] Token reserve: LLM calls per question bounded in one CONFIG block (rounds/queries/lenses); true token accounting deferred.** [Pirohuni]
20. **[done] Deterministic authoritative EVIDENCE banner (hygiene.evidence_state) the LLM is told it cannot override.** [Pirohuni]
21. **[done] Graceful degradation: every lane falls back (ensemble->fallback->template) and never crashes the run; hard abstain not forced (0.5 + loud banner is lower-harm on Metaculus).** [all]
22. **[done] Structured-output salvage (brace-balanced extraction + repair) before dropping a member.** [nostream]
23. **[done] INCIDENTS.md + tests/test_brain.py (17 golden-replay cases over every deterministic seam).** [Pirohuni]
24. **[blocked-on-key] Multi-model via OpenRouter + prompt caching.** [Panshul]

## Explicitly NOT doing
- A learned stacker / meta-combiner: all three tested it; none beat median. Keep
  median (+ the tiebreaker in #2).

## Methodology risk (see chat 2026-10-09)
The dialectical-HM + game-theory brain is our differentiator but is ONE lens →
systematic, correlated blind spots + inside-view overconfidence. Mitigation is
items #1 (diverse paths), #4 (sealed base rate), #9 (market floors/ceilings),
#17 (falsification targets the lens's blind spots), and #5 (measure whether the
lens actually adds value, don't assume).
