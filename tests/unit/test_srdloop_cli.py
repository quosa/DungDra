"""Unit tests for the command line: help, the list filters, and person decisions as commits."""

import subprocess

import pytest

from scripts.srdloop import __main__ as CLI
from scripts.srdloop import rulings as Ru
from scripts.srdloop import tickets as T
from tests.unit.test_srdloop_gates import git_repo


def cli(capsys, *argv):
    code = CLI.main(list(argv))
    return code, capsys.readouterr().out


def last_commit():
    return subprocess.run(
        ["git", "log", "--format=%s", "-1"], capture_output=True, text=True, check=True
    ).stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    git_repo(tmp_path, {"README.md": "x\n"})
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_top_level_help_lists_every_command_and_each_command_has_its_own(capsys):
    with pytest.raises(SystemExit):
        CLI.main(["--help"])
    top = capsys.readouterr().out
    for name in ("status", "run", "dev", "ticket", "ruling", "review", "report", "mutate"):
        assert f"    {name} " in top
    with pytest.raises(SystemExit):
        CLI.main(["ticket", "--help"])
    ticket = capsys.readouterr().out
    assert all(f"    {a} " in ticket for a in ("list", "show", "create", "reopen", "void", "waive", "cap"))


def test_ticket_list_hides_finished_ones_unless_all(repo, capsys):
    T.create("bug", "GLOSS.x", "wrong", [])
    done = T.create("infra", "GLOSS.x", "no map", [])
    done["status"] = "fixed"
    T.save(done)
    _, out = cli(capsys, "ticket", "list")
    assert "T-1 " in out and "T-2 " not in out and "(1 fixed or void not shown" in out
    _, out = cli(capsys, "ticket", "list", "--all", "--kind", "infra")
    assert "T-2 " in out and "T-1 " not in out


def test_person_decisions_on_tickets_are_committed_with_their_reason(repo, capsys):
    code, out = cli(
        capsys, "ticket", "create", "bug", "SPELL.bless", "SRD: once; engine: twice", "--test", "t::a"
    )
    assert code == 0 and T.load("T-1")["tests"] == ["t::a"]
    assert last_commit().strip() == "ticket: T-1 created (bug, SPELL.bless): SRD: once; engine: twice"
    cli(capsys, "ticket", "void", "T-1", "--reason", "duplicate of T-0")
    assert T.load("T-1")["status"] == "void" and last_commit().strip() == "ticket: T-1 void: duplicate of T-0"
    tk = T.load("T-1")
    tk["attempts"] = 3
    T.save(tk)
    cli(capsys, "ticket", "reopen", "T-1", "--reason", "the scenario was wrong")
    assert (T.load("T-1")["status"], T.load("T-1")["attempts"]) == ("open", 0)
    code, _ = cli(capsys, "ticket", "reopen", "T-1", "--reason", "again")
    assert code == 1  # already open
    cli(capsys, "ticket", "cap", "T-1", "12")
    assert T.load("T-1")["cap_usd"] == 12.0 and last_commit().strip() == "ticket: T-1 fixer cap $12.00"
    cli(capsys, "ticket", "waive", "T-1", "diff_coverage", "--reason", "a person approved")
    assert T.load("T-1")["waive"] == {"diff_coverage": "a person approved"}
    _, out = cli(capsys, "ticket", "show", "T-1")
    assert "test: t::a" in out and "- reopened: was=void, reason=the scenario was wrong" in out
    with pytest.raises(SystemExit):
        CLI.main(["ticket", "void", "T-1"])  # a decision without a reason is refused
    assert cli(capsys, "ticket", "show", "T-9")[0] == 1


def test_ruling_and_review_lists_show_only_what_waits(repo, capsys):
    Ru.create("GLOSS.x", "two at once?", "no", [])
    done = Ru.create("GLOSS.x", "Tiny?", "never", [])
    done["status"] = "accepted"
    Ru.save(done)
    _, out = cli(capsys, "ruling", "list")
    assert "P-1 " in out and "P-2 " not in out and "(1 decided not shown" in out
    assert "P-2 " in cli(capsys, "ruling", "list", "--all")[1]
    assert "nothing waiting for review" in cli(capsys, "review", "list")[1]


def test_help_is_the_same_as_dash_dash_help_at_any_depth(capsys):
    for args in ([], ["help"], ["--help"]):
        with pytest.raises(SystemExit):
            CLI.main(args)
        out = capsys.readouterr().out
        assert "    ticket " in out and "    help " in out
    with pytest.raises(SystemExit):
        CLI.main(["help", "ticket", "create"])
    via_help = capsys.readouterr().out
    with pytest.raises(SystemExit):
        CLI.main(["ticket", "create", "--help"])
    assert via_help == capsys.readouterr().out and "--test NODEID" in via_help
