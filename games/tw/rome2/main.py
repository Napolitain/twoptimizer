"""Run the Rome II public-reference economic comparison."""

from games.tw.rome2.benchmark import main

if __name__ == "__main__":
    from twoptimizer.cli import run_cli

    raise SystemExit(run_cli(main))
