"""Interface selection; game parsers and workers use the same case service."""

import importlib
import sys

from twoptimizer.cli import run_cli
from twoptimizer.registry import command_help, command_named


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
    if (command := command_named(args[0])) is not None:
        return run_cli(importlib.import_module(command.module).main, args[1:])
    if args in (["--help"], ["-h"]):
        print(
            "Usage: twoptimizer [tui | GAME [options]]\n\nNo arguments opens the"
            " interactive terminal UI.\n\nCLI commands:\n"
            + "\n".join(f"  {name:<17}{description}" for name, description in command_help())
            + "\n\nUse twoptimizer GAME --help for "
            "existing CLI options."
        )
        return 0
    print(f"Unknown command: {args[0]}. Use twoptimizer --help.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
