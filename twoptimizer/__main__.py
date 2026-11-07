"""No arguments opens the TUI; subcommands forward to the existing CLIs."""

import importlib
import sys

COMMANDS = {
    "rome2": "games.tw.rome2.benchmark",
    "shogun2": "games.tw.shogun2.benchmark",
    "attila": "games.tw.benchmark",
    "attila-factions": "games.tw.faction_comparison",
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
        importlib.import_module(COMMANDS[args[0]]).main(args[1:])
        return 0
    if args in (["--help"], ["-h"]):
        print(
            "Usage: twoptimizer [tui | GAME [options]]\n\nNo arguments opens the"
            " interactive terminal UI.\n\nCLI commands:\n  rome2             Rome"
            " II comparisons\n  shogun2           Shogun 2 comparisons\n  attila"
            "            Attila province optimization\n  attila-factions   "
            "Attila faction comparisons\n\nUse twoptimizer GAME --help for "
            "existing CLI options."
        )
        return 0
    print(f"Unknown command: {args[0]}. Use twoptimizer --help.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
