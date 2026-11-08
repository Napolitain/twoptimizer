"""Interface selection; game parsers and workers use the same case service."""

import importlib
import sys

from twoptimizer.cli import run_cli

COMMANDS = {
    "rome2": "games.tw.rome2.benchmark",
    "shogun2": "games.tw.shogun2.benchmark",
    "attila": "games.tw.benchmark",
    "attila-factions": "games.tw.faction_comparison",
    "hoi4": "games.hoi4.cli",
}


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args == ["tui"]:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            print(
                "The TUI needs an interactive terminal. Use twoptimizer --help for CLI commands.",
                file=sys.stderr,
            )
            return 2
        from twoptimizer.tui import OptimizerApp

        OptimizerApp().run()
        return 0
    if args[0] in COMMANDS:
        return run_cli(importlib.import_module(COMMANDS[args[0]]).main, args[1:])
    if args in (["--help"], ["-h"]):
        print(
            "Usage: twoptimizer [tui | GAME [options]]\n\nNo arguments opens the"
            " interactive terminal UI.\n\nCLI commands:\n  rome2             Rome"
            " II comparisons\n  shogun2           Shogun 2 comparisons\n  attila"
            "            Attila province optimization\n  attila-factions   "
            "Attila faction comparisons\n  hoi4 data         HoI4 public reference data"
            "\n  hoi4 plan-check   Review hourly planning input structure"
            "\n\nUse twoptimizer GAME --help for "
            "existing CLI options."
        )
        return 0
    print(f"Unknown command: {args[0]}. Use twoptimizer --help.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
