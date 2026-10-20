# Seams: what unit tests may replace

Unit tests (`tests/unit/`) test one component of `dungdra/` at a time. They may replace only
these boundaries, and never the module under test itself. `python -m scripts.srdloop dev-gate`
rejects a `tests/unit/test_<module>.py` that patches anything inside `dungdra.<module>` except
the names below.

| Seam | How to replace it |
|---|---|
| Randomness | `game.dice.force_str("d20=[…]")`; a `random` attribute only if a module draws its own numbers |
| Player choices | `game.answer(key, value)` |
| Input and output | `input`, `open` |
| Time | `time` |

The SRD and scenario suites (`tests/srd/`, `tests/scenarios/`) replace nothing: they run the
real engine, with forced dice and pre-answered choices.
