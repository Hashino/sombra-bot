"""Prompt templates for sombra-bot's structured forecasting brain.

These encode the owner's design: forecast by building a structured model of the
situation rather than asking an LLM for a number in one shot.

- STRATEGIC lane: enumerate actors -> map their material interests through
  dialectical historical materialism -> map relations -> solve each actor's
  best response via game theory -> project the equilibrium -> read the outcome.
- MEASUREMENT lane: anchor on base rates / reference classes / recent trend.
- FALSIFY: the sombra move — actively try to break the analysis before trusting
  it, and revise if the counter-case has teeth.

Each prompt ends by making the directional read explicit so the template's
downstream forecast step (which turns reasoning into a probability or a
percentile distribution) has a sharp signal to quantify.
"""

ROUTE = """You are triaging a forecasting question into one of two analysis methods.

- "strategic": the outcome is primarily DECIDED by identifiable actors making
  choices (a government, party, court, central bank, company, military, bloc).
  Examples: elections, legislation, rulings, sanctions, M&A, resignations, war moves.
- "measurement": the outcome is an impersonal quantity read off the world, not
  chosen by any single actor. Examples: a commodity settle price, an inflation
  rate, a disease level, a market index, a physical reading.

Question: {q}
Resolution criteria: {rc}

Answer with EXACTLY one word: strategic OR measurement."""

STRATEGIC = """You are a cold, structural analyst forecasting a real-world question. Do NOT
moralize or hedge. Build the forecast in explicit, numbered layers.

QUESTION: {q}
RESOLUTION CRITERIA: {rc}
FINE PRINT: {fp}
TODAY: {today}

RESEARCH (use as evidence, not as gospel):
{news}

Produce the analysis in these layers, each labeled:

1. ACTORS. Enumerate every actor whose choices materially bear on this outcome.
   Name who really holds power over the result (de facto, not by title).

2. INTERESTS (dialectical historical materialism). For each actor, state its
   material position — what it must do to preserve or expand its power and
   resources. Ground interest in structural position (class, capital, state
   apparatus, electoral base, institutional survival), not stated rhetoric.
   Note the internal contradictions that constrain each actor.

3. RELATIONS. Map alliances, dependencies, leverage and antagonisms between the
   actors. Who can coerce, bribe, or veto whom.

4. GAME. Treat this as a game. For each actor, give its highest-payoff action
   given what the others will rationally do. Identify the equilibrium — the
   combination of actions from which no actor gains by deviating. State the key
   assumption the equilibrium rests on.

5. PROJECTION. Play the equilibrium forward to the resolution date. What
   concretely happens, and does it satisfy the resolution criteria?

6. READ. State the direction and strength of your conclusion in plain terms
   (e.g. "clearly yes", "leans no", "near coin-flip, slight yes"), and name the
   single biggest thing that would flip it."""

MEASUREMENT = """You are a disciplined quantitative forecaster. Avoid narrative; anchor on data.

QUESTION: {q}
RESOLUTION CRITERIA: {rc}
FINE PRINT: {fp}
TODAY: {today}

RESEARCH (use as evidence):
{news}

Work in labeled steps:

1. REFERENCE CLASS. What is the base rate / historical distribution for this
   kind of quantity? Give the typical range and central tendency.

2. CURRENT STATE. The latest actual value(s) and the recent trend/volatility
   from the research. Cite the number and its date.

3. DRIFT. From now to the resolution date, how much can this move? Account for
   seasonality, mean-reversion, momentum, and known scheduled events.

4. READ. State your central estimate and an honest spread (how wide the
   plausible range is), and the single biggest source of uncertainty."""

FALSIFY_ATTACK = """You are a hostile red-team forecaster. Your only job is to BREAK the analysis
below — find the strongest case that its READ is wrong.

QUESTION: {q}
ANALYSIS:
{dossier}

RESEARCH AVAILABLE:
{news}

List up to 4 concrete, specific reasons the READ could be wrong: a wrong
premise, an ignored actor, a base-rate error, a status-quo bias, a
misread of the resolution criteria, or recent evidence pointing the other way.
Be specific and evidence-based; do not invent facts. If the analysis is in fact
robust, say so and explain why the obvious attacks fail."""

FALSIFY_REVISE = """You wrote this analysis, then a red-team raised the critique below. Revise
honestly: if a critique has real force, move your READ toward it; if it is weak,
say why and keep your READ. Do not revise just to appease.

QUESTION: {q}

ORIGINAL ANALYSIS:
{dossier}

RED-TEAM CRITIQUE:
{attack}

Output the FINAL analysis, keeping the same labeled layers, ending with a READ
that now reflects the surviving evidence. Make the final READ unambiguous about
direction and strength."""


FALSIFY_QUERIES = """You are red-teaming the forecast below. Produce web-search queries whose
results could DISPROVE its READ — target the weakest premise, the most
resolution-critical fact, or recent developments that might reverse it.

QUESTION: {q}
ANALYSIS:
{dossier}

Output up to 4 search queries, ONE PER LINE, no numbering, no commentary. Each
query should be specific and recent-evidence-seeking. If the analysis cannot be
meaningfully attacked with new evidence, output the single line: NONE"""

FALSIFY_JUDGE = """You gathered fresh evidence to test a forecast. Decide, honestly, whether the
new evidence should MOVE the analysis's READ (its direction or strength).

QUESTION: {q}
CURRENT READ (from the analysis):
{dossier}

FRESH EVIDENCE GATHERED:
{evidence}

First line MUST be exactly "MOVES: YES" or "MOVES: NO".
Then 2-4 sentences: what in the evidence moves it (or why the evidence, despite
looking relevant, does not change the READ). Do not move the READ for evidence
that merely restates what was already known."""
