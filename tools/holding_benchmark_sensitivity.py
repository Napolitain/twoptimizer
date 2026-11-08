"""Run longer per-case solver allowances after an equal-budget benchmark matrix.

These diagnostics use different total allowances than the primary matrix.
They must not be presented as fair speed comparisons with that matrix.
"""

import argparse
import asyncio
import hashlib
import json
import math
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from tools.holding_benchmark import SOLVERS, Limits, environment, group_summary, run_sample
from twoptimizer.requests import default_config, make_jobs


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--game", action="append", choices=("attila", "rome2", "shogun2"))
    cli.add_argument("--algorithm", choices=SOLVERS, default="cp-sat")
    cli.add_argument("--seconds-per-case", type=float, default=1)
    cli.add_argument("--mode", choices=("independent", "joint"), default="independent")
    cli.add_argument("--wall-seconds", type=float, default=180)
    cli.add_argument("--memory-mib", type=float, default=2048)
    cli.add_argument("--revision")
    cli.add_argument("--output-directory", type=Path, required=True)
    args = cli.parse_args(argv)
    if any(
        not math.isfinite(value) or value <= 0
        for value in (args.seconds_per_case, args.wall_seconds, args.memory_mib)
    ):
        cli.error("Resource limits must be finite and positive")
    if not Path("/proc/self/status").exists():
        cli.error("This benchmark requires Linux /proc for its worker memory guard")
    args.output_directory.mkdir(parents=True, exist_ok=True)
    for game in args.game or ("attila", "rome2"):
        config = replace(
            default_config(game),
            provinces=("all",),
            algorithm=args.algorithm,
            joint=args.mode == "joint",
        )
        count = len(make_jobs(config)[0])
        limits = Limits(args.seconds_per_case * count, args.wall_seconds, args.memory_mib)
        sample = asyncio.run(run_sample(config, limits))
        report = {
            "schema_version": 1,
            "created_at_utc": datetime.now(UTC).isoformat(),
            "environment": environment(args.revision),
            "sensitivity_driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "limits": vars(limits),
            "method": (
                "One diagnostic sample, fresh worker reused across its cases, "
                "fixed per-case solver allowance (which may include conversion). "
                "Different aggregate allowance from the primary matrix; no fair speed comparison."
            ),
            "groups": [
                {
                    "size": "all",
                    "request": config.to_dict(),
                    "samples": [sample],
                    "summary": group_summary([sample]),
                }
            ],
        }
        suffix = "-joint" if args.mode == "joint" else ""
        if args.algorithm != "cp-sat":
            suffix += f"-{args.algorithm}"
        path = args.output_directory / f"holding-performance-sensitivity-{game}{suffix}.json"
        path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(
            f"{game} {args.algorithm}: {sample['completion']} {sample['wall_seconds']:.3f}s "
            f"{sample['summary']['statuses']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
