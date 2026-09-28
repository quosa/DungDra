"""Interactive command-line play: `python -m dungdra` (or `dungdra`)."""
from __future__ import annotations

import argparse
import os
import sys

from .play import Play


def interactive_decider(game, who, key, options, default, prompt):
    """Ask the human at the keyboard whenever the rules offer a choice (Reactions, Luck ...)."""
    if not prompt:
        return default
    print(f"\n  ? {prompt}")
    if options and all(isinstance(o, bool) for o in options):
        ans = input(f"    [y/n, default {'y' if default else 'n'}] > ").strip().lower()
        if not ans:
            return default
        return ans.startswith("y")
    shown = [o for o in (options or [])]
    for i, o in enumerate(shown):
        print(f"    {i}: {o}")
    ans = input(f"    choose a number (Enter for default {default!r}) > ").strip()
    if not ans:
        return default
    try:
        return shown[int(ans)]
    except (ValueError, IndexError):
        return default


def main(argv=None):
    ap = argparse.ArgumentParser(description="DungDra: a fifth-edition-compatible solo adventure")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--llm", action="store_true", help="use Claude to interpret free-form input "
                    "(needs ANTHROPIC_API_KEY)")
    ap.add_argument("--gm-log", action="store_true", help="also print GM-only log entries")
    args = ap.parse_args(argv)
    llm = None
    if args.llm:
        from .llm import ClaudeInterpreter
        llm = ClaudeInterpreter()
    p = Play(seed=args.seed, decider=interactive_decider, llm=llm)
    if args.gm_log:
        p.game.log.listeners.append(lambda e: print("   [GM] " + str(e)) if e.visibility == "gm" else None)
    print(p.begin())
    print("(Type 'help' for examples, 'quit' to leave.)")
    while True:
        try:
            line = input("\n> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.strip().lower() in ("quit", "exit"):
            break
        if line.strip().lower() == "help":
            print(HELP)
            continue
        print(p.say(line))
    print("Farewell, adventurer.")


HELP = """Examples:
  use the sample party            begin the adventure            status / sheet / look
  BROM attacks the goblin with his longsword        LIDDA throws a dagger at goblin 2
  MIALEE casts magic missile at goblin 3            JOZAN casts healing word on MIALEE
  LIDDA uses cunning action to hide                 BROM uses second wind
  end turn      continue      short rest      long rest      travel 6 miles at normal pace through forest on the road
  LIDDA picks the lock      MIALEE examines the floor      BROM wedges a spike into the pit lid
"""

if __name__ == "__main__":
    sys.exit(main())
