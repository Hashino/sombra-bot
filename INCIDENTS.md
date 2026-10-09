# INCIDENTS

Production forecasting incidents — a bad or broken forecast, a crash on a live
question, a mis-parse, a wrong lane. The point (improvement #23): every incident
becomes a permanent regression test in `tests/test_brain.py`, keyed to the
Metaculus question id, so the same failure can never ship twice.

## How to log one

For each incident add an entry below, newest first:

```
### <date> — <question id / url> — <one-line symptom>
- **What happened:** observed bad behavior (the forecast, the crash, the parse).
- **Root cause:** the seam that failed (prompt / parse / compose / aggregate /
  numeric / submission / routing).
- **Fix:** what changed.
- **Regression test:** the test name added in tests/test_brain.py (or why none).
```

Then add the reproducing case to `tests/test_brain.py` and run
`python3 tests/test_brain.py` before committing.

---

_No incidents logged yet — the bot has not run on live questions
(waiting on OPENROUTER_API_KEY). First live MiniBench round is the first chance
to populate this._
