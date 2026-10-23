"""Unit tests for dungdra.cli: the terminal loop and its choice prompts."""

import builtins

import pytest

from dungdra import cli


def _no_more_input(prompt=""):
    raise EOFError


def test_end_of_input_at_a_choice_takes_the_default(monkeypatch):
    monkeypatch.setattr(builtins, "input", _no_more_input)
    assert cli.interactive_decider(None, None, "swap", ["a", "b"], "b", "Swap?") == "b"
    assert cli.interactive_decider(None, None, "luck", [True, False], True, "Reroll?") is True


def test_a_session_runs_until_quit_without_writing_an_error_log(monkeypatch, tmp_path, capsys):
    lines = iter(["use the sample party", "begin the adventure", "status", "quit"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(lines))
    log = tmp_path / "errors.log"
    cli.main(["--seed", "3", "--error-log", str(log)])
    out = capsys.readouterr().out
    assert "BROM: HP" in out and out.rstrip().endswith("Farewell, adventurer.")
    assert not log.exists()


def test_bug_details_are_appended_to_the_error_log(tmp_path):
    log = tmp_path / "errors.log"
    assert cli.save_errors(log, ["> first\nTraceback"]) == f"(The details are in {log}.)"
    cli.save_errors(log, ["> second\nTraceback"])
    assert log.read_text().splitlines() == ["> first", "Traceback", "> second", "Traceback"]


def test_an_adventure_is_chosen_by_name_or_path(monkeypatch, tmp_path, capsys):
    lines = iter(["use the sample party", "begin the adventure", "map", "quit"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(lines))
    cli.main(["--seed", "3", "--adventure", "goblin-trail", "--error-log", str(tmp_path / "e.log")])
    assert "Map of The Goblin Trail:\n  Millbrook (you are here)" in capsys.readouterr().out


def test_an_adventure_that_isnt_there_stops_before_the_game_starts(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--adventure", "no-such-adventure"])
    assert "no adventure called 'no-such-adventure'" in capsys.readouterr().err


def test_the_llm_option_says_it_isnt_built_yet(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--llm"])
    assert "--llm isn't built yet" in capsys.readouterr().err
