"""The SRD rule suite: tests the test-designer agent derives from the SRD, one or more per clause.

Two rules hold for every test here:
- forced dice must all be used: a test that forces a roll the code never makes didn't test
  what it set up (checked after every passing test);
- no mocks: the real engine only; randomness comes from forced dice, choices from game.answer.
"""

import pytest

from dungdra.game import Game


def _unused_dice(item) -> dict[str, list[int]]:
    left: dict[str, list[int]] = {}
    for value in item.funcargs.values():
        games = [value] if isinstance(value, Game) else [getattr(value, "game", None)]
        for g in games:
            if isinstance(g, Game):
                for sides, queue in g.dice.forced.items():
                    if queue:
                        left.setdefault(f"d{sides}", []).extend(queue)
    return left


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.passed and not hasattr(report, "wasxfail"):
        left = _unused_dice(item)
        if left:
            report.outcome = "failed"
            report.longrepr = (
                f"forced dice were never rolled: {left} (the test didn't exercise what it set up)"
            )
