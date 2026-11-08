"""Repeat serial, uninstrumented engine runs with reproducible scenario settings."""

import argparse
import hashlib
import json
import platform
from dataclasses import asdict
from pathlib import Path
from statistics import median
from time import perf_counter

from twoptimizer.catalog import choices
from twoptimizer.models import RunConfig
from twoptimizer.service import solve_case


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--game", choices=("attila", "rome2", "shogun2"), default="attila")
    cli.add_argument("--repeat", type=int, default=3)
    cli.add_argument("--workers", type=int, default=1)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    if args.repeat < 1:
        cli.error("repeat must be positive")
    catalog = choices(args.game)
    config = RunConfig(
        game=args.game,
        faction=catalog["default_faction"],
        province=catalog["default_province"],
        research=catalog["default_research"],
        algorithm="cp-sat",
        workers=args.workers,
    )
    samples = []
    signatures = set()
    for _ in range(args.repeat):
        started = perf_counter()
        result = solve_case(config)
        elapsed = perf_counter() - started
        stable = {key: result[key] for key in ("income", "metrics", "buildings")}
        stable["status"] = result["solver"]["status"]
        signatures.add(hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest())
        samples.append({"wall_seconds": elapsed, "timings": result["timings"], **stable})
    if len(signatures) != 1:
        raise RuntimeError("Repeated runs disagree; inspect results before comparing speed")
    report = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "request": asdict(config),
        "result_sha256": signatures.pop(),
        "median_seconds": median(s["wall_seconds"] for s in samples),
        "samples": samples,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(f"{args.game}: median {report['median_seconds']:.3f}s ({args.repeat} runs)")


if __name__ == "__main__":
    main()
