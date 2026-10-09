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

0. SEALED BASE RATE (outside view). Before ANY actor reasoning, name the
   reference class and state how often this KIND of outcome happens (e.g. how
   often announced-by-date releases ship on time, how often courts meet a
   self-imposed deadline, how often incumbents in this position survive). Commit
   to a numeric prior P0 now and FREEZE it — you may not silently revise P0 later
   to match your conclusion. Everything below is an argument about how far to
   move off P0, and that move must be earned, not assumed.

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

6. READ. State the conclusion EXPLICITLY as a move from the sealed prior P0,
   gated by this rubric:
     - STRONG evidence (decisive, well-sourced, resolution-critical) → a large
       move off P0 is justified.
     - MODERATE evidence (suggestive, contested, or indirect) → a modest move.
     - WEAK / absent evidence → stay at or very near P0.
   Report P0, the final probability, and which rubric tier the actor dynamics
   earned. Name the single biggest thing that would flip the READ."""

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


FALSIFY_QUERIES = """You are red-teaming the forecast below. Produce web-search queries that could
MOVE its READ — in EITHER direction. Do not only seek disconfirming evidence;
also seek the strongest CONFIRMING fact that would harden it. Spend at least one
query probing this analysis's specific BLIND SPOTS, because it was built from a
material-interest / game-theory lens that systematically under-weights:
  - non-material motives (ideology, personal/ego, reputation, spite, belief);
  - institutional / procedural / accidental paths (bureaucratic inertia, a legal
    technicality, a deadline slip, a resignation, an exogenous shock, scandal);
  - the possibility that the resolution criteria hinge on a detail the strategic
    story ignores.

QUESTION: {q}
ANALYSIS:
{dossier}

Output up to 4 search queries, ONE PER LINE, no numbering, no commentary. Each
specific and recent-evidence-seeking; mix confirming, disconfirming, and
blind-spot probes. If the analysis genuinely cannot be tested with new evidence,
output the single line: NONE"""

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



## ---- research orchestration (#11/#12): plan the evidence, then check for it ----

EVIDENCE_PLAN = """You are planning the research for a forecasting question, BEFORE searching.
Name the single concrete fact or value that the question RESOLVES on — the one
thing we must find to settle it — and the best places to find it.

QUESTION: {q}
RESOLUTION CRITERIA: {rc}
FINE PRINT: {fp}

Output ONLY JSON:
{{
  "resolving_value": "<the one fact/number/event that decides YES vs NO>",
  "queries": ["<2-4 specific search queries that would surface it>"],
  "authoritative_sources": ["<the official source(s) the criteria point to, if any>"]
}}"""

ARTIFACT_CHECK = """You searched for the fact that resolves a forecasting question. Judge honestly
whether the evidence actually CONTAINS that fact.

RESOLVING VALUE WE NEEDED: {value}
EVIDENCE GATHERED:
{evidence}

First line MUST be exactly one of: "FOUND", "PARTIAL", "MISSING".
If PARTIAL or MISSING, a second line "RETRY: <one focused search query>" that
would most likely close the gap. Nothing else."""


ESTIMATE_BINARY = """Convert the completed ANALYSIS into the INGREDIENTS of a probability. Do NOT
state a final probability — a calculator composes it from what you give.

QUESTION: {q}
RESOLUTION CRITERIA: {rc}
ANALYSIS:
{dossier}

Output ONLY a JSON object (no prose, no fence):
{{
  "base_rate": <0-1>,              // outside-view prior from the base-rate layer
  "branches": [                    // mutually-exclusive scenarios for how it resolves; weights should sum to ~1
    {{"desc": "<short>", "w": <0-1>, "p_yes": <0-1>}}  // w=chance of this scenario; p_yes=P(YES | this scenario)
  ],
  "market_floor": <0-1 or null>,   // if a prediction market ENTAILS a lower bound on P(YES), else null
  "market_ceiling": <0-1 or null>, // upper bound if entailed, else null
  "inside_confidence": <0-1>,      // how much the structural analysis should outweigh the base rate
  "mass_yes": <0-1>,               // INDEPENDENTLY of the branches above, your holistic P(YES). This is a self-check.
  "note": "<key assumption>"
}}
If resolution hinges on one scenario, use one branch. Keep probabilities honest."""

OUTSIDE_BINARY = """You are the OUTSIDE-VIEW member of a forecasting panel. IGNORE the narrative
and the specific actors. Answer only from the reference class: how often does
this KIND of event resolve YES, historically? Resist being moved by vivid recent
detail — that is another member's job.

QUESTION: {q}
RESOLUTION CRITERIA: {rc}
RESEARCH (for base rates only):
{research}

Output ONLY JSON:
{{"base_rate": <0-1>, "branches": [{{"desc":"reference class","w":1,"p_yes":<0-1>}}],
  "inside_confidence": 0.15, "mass_yes": <0-1, ~= your base rate>, "note": "<the reference class used>"}}"""

MARKET_BINARY = """You are the MARKET & STATUS-QUO member of a forecasting panel. Anchor on (a)
any prediction-market prices in the research and (b) a strong status-quo prior
(most things that need a change to resolve YES do NOT happen by the deadline).
Convert market signals into bounds, not gospel.

QUESTION: {q}
RESOLUTION CRITERIA: {rc}
RESEARCH:
{research}

Output ONLY JSON:
{{"base_rate": <0-1 status-quo prior>, "branches": [{{"desc":"market/status-quo","w":1,"p_yes":<0-1>}}],
  "market_floor": <0-1 or null>, "market_ceiling": <0-1 or null>,
  "inside_confidence": 0.5, "mass_yes": <0-1>, "note": "<markets cited or status-quo reasoning>"}}"""

## ---- numeric lane: one smooth component per resolution scenario / route ----

_NUMERIC_JSON = """Output ONLY a JSON object (no prose, no fence):
{{
  "components": [            // ONE per genuinely distinct resolution scenario; weights w should sum to ~1
    {{"desc": "<short>", "w": <0-1>,
      "family": "normal" | "lognormal" | "truncated_normal",
      "mean": <num>, "sd": <num>,          // for normal / truncated_normal (sd = ~1 std dev of the value)
      "mu": <num>, "sigma": <num>,         // for lognormal (natural-log space); omit the pair you don't use
      "lo": <num or null>, "hi": <num or null>}}   // only for truncated_normal
  ],
  "note": "<the key driver of the spread>"
}}
Use a SEPARATE component for each scenario that lands the value in a different
region (do not average distinct outcomes into one wide blob). Make each sd/sigma
honest about within-scenario uncertainty. Units: {unit}."""

NUMERIC_STRUCTURAL = """Convert the completed ANALYSIS into a MIXTURE of distribution components — one
per distinct way the question resolves (map them from the branches/equilibria in
the analysis). A calculator turns these into percentiles; do NOT emit percentiles.

QUESTION: {q}
RESOLUTION CRITERIA: {rc}
ANALYSIS:
{dossier}

""" + _NUMERIC_JSON

NUMERIC_OUTSIDE = """You are the OUTSIDE-VIEW member. Ignore the specific narrative; give the
reference-class distribution for this quantity: where have comparable cases
historically landed? One or two components describing that empirical spread.

QUESTION: {q}
RESOLUTION CRITERIA: {rc}
RESEARCH (for base rates / history only):
{research}

""" + _NUMERIC_JSON

NUMERIC_STATUSQUO = """You are the STATUS-QUO / TREND member. Anchor on the latest actual value in the
research and project it to the resolution date with only the current trend and
normal volatility — no dramatic scenarios. Usually ONE component centered on that
projection, with sd reflecting how much the series actually moves over this horizon.

QUESTION: {q}
RESOLUTION CRITERIA: {rc}
RESEARCH:
{research}

""" + _NUMERIC_JSON


JUDGE_BINARY = """Three forecasting panel members disagree sharply on this question. Read their
reasoning and synthesize ONE calibrated probability. Favor the member whose
evidence is strongest; do not just average. Beware the elegant-narrative member
being confidently wrong against the base rate.

QUESTION: {q}
MEMBERS:
{members}

Output ONLY: "Probability: NN%" then one sentence of justification."""


## ---- multiple-choice lane: a probability over a fixed option set ----

_MC_JSON = """The options are EXACTLY: {options}
Output ONLY a JSON object mapping each option name to its probability (0-1),
using the option names verbatim. They should sum to ~1. Leave some moderate mass
on unlikely options (surprises happen); never hard-zero an option.
{{ "<option>": <0-1>, ... , "note": "<key driver>" }}"""

ESTIMATE_MC = """Convert the completed ANALYSIS into a probability distribution over the options.
Map the branches/equilibria in the analysis onto the options.

QUESTION: {q}
RESOLUTION CRITERIA: {rc}
ANALYSIS:
{dossier}

""" + _MC_JSON

OUTSIDE_MC = """You are the OUTSIDE-VIEW member. From the reference class / base rates only —
how often does each KIND of option win historically? Ignore the vivid specifics.

QUESTION: {q}
RESOLUTION CRITERIA: {rc}
RESEARCH (base rates only):
{research}

""" + _MC_JSON

MARKET_MC = """You are the MARKET & STATUS-QUO member. Anchor on any market/poll signals in the
research and a status-quo prior (the option representing "no change" gets extra
weight). Convert signals into probabilities, not gospel.

QUESTION: {q}
RESOLUTION CRITERIA: {rc}
RESEARCH:
{research}

""" + _MC_JSON

JUDGE_MC = """Panel members disagree on this multiple-choice question. Synthesize ONE
distribution over the options. Favor the strongest evidence; keep moderate mass
on surprises; do not hard-zero.

QUESTION: {q}
OPTIONS (verbatim): {options}
MEMBERS:
{members}

Output ONLY a JSON object mapping each option to its probability (0-1), summing
to ~1, plus a "note"."""
