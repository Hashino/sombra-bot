# sombra-bot — architecture

A Metaculus FutureEval forecasting bot. Base harness = the official
`metac-bot-template` + `forecasting-tools` (question pulling, 201-point CDF,
submission, required reasoning comment, 5x-median ensemble, GitHub Actions).
On top of that we graft a differentiated forecasting brain.

## Core idea (owner's design)
For each question, build the forecast *structurally*, not as a single prompt:

1. **Actor graph** — enumerate every actor whose choices bear on the outcome.
2. **Interests** — map each actor's material interests via dialectical
   historical materialism (who holds power in fact, what they must do to keep it).
3. **Relations** — alliances, dependencies, antagonisms between actors.
4. **Game-theoretic resolution** — the highest-payoff action for each actor
   given the others; find the equilibrium.
5. **Falsification loop (ported from `sombra/engine/verify.py`)** — generate
   queries that try to *break* each premise; search; if the evidence moves the
   estimate, refine. Bounded iterations, early stop.
6. **Projection → probability** — model what happens when all actors play their
   equilibrium actions; translate into a calibrated probability / distribution.

## Router (implementation detail)
Not every question is actor-driven. A router classifies each question:
- **actor/strategic** (elections, policy, court rulings, company/state action)
  → the full actor→interests→game-theory→falsification pipeline above.
- **impersonal/measurement** (commodity prices, epidemiology, physical
  readings, indices) → base-rate / reference-class / time-series reasoning,
  still passed through the falsification loop.

## Status
- [x] Template base (plumbing works out of the box)
- [ ] OPENROUTER_API_KEY secret (owner adds, from the participation form)
- [x] Router node (heuristic + LLM tiebreaker)
- [x] Actor-model forecaster + measurement lane
- [x] Falsification loop — multi-round, fresh web re-search, two-sided + blind-spot targeted
- [x] Diverse 3-lens panel (actor/game-theory + outside-view + market/status-quo), median + tiebreaker-judge on wide spread
- [x] Answer-space witness (member states mass_yes; code reverts toward prior on mismatch)
- [x] Sealed base-rate gate (P0 frozen; move off P0 earned via strong/moderate/weak rubric)
- [x] Composed binary probability (branch-mixture / noisy-OR; markets as floor/ceiling) — computed, not guessed
- [x] Numeric lane — mixture of named components per route → monotone CDF → quantile-space blend → tail widen → bound clamp
- [x] Multiple-choice lane — per-option median of the panel, floor + renormalize, tiebreaker-judge
- [x] Calibration (shrink toward 0.5, scaled by resolution horizon)
- [x] Research orchestration — evidence plan + resolution-source read + artifact-check gap loop (shared bundle, time-boxed)
- [x] Hygiene — deterministic evidence banner, date-leakage filter, parser salvage, graceful degradation on every lane
- [x] Regression — tests/test_brain.py (17 golden-replay cases) + INCIDENTS.md
- [ ] Learned calibration (Platt) + offline eval loop — blocked on first resolved MiniBench round
- [ ] Multi-model LINEAGE ensemble + prompt caching (reasoning-PATH diversity already live) — set when key lands
- [ ] Point the Actions workflow at sombra_bot.py (done at merge)
