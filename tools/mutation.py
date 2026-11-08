"""Reject incomplete/surviving mutation results; --scope explicitly narrows a run."""

import argparse
import json
import subprocess
import sys
from collections import Counter
from fnmatch import fnmatchcase
from pathlib import Path


def scoped_stats(patterns: list[str]) -> dict:
    """Count every selected mutant, including unrun or failed ones."""
    result = subprocess.run(
        ["mutmut", "results", "--all", "true"], check=True, capture_output=True, text=True
    )
    counts: Counter[str] = Counter()
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        name, separator, status = line.strip().partition(": ")
        if not separator:
            raise ValueError(f"Unrecognized mutation result: {line}")
        if any(fnmatchcase(name, pattern) for pattern in patterns):
            counts[status.replace(" ", "_")] += 1
    stats = dict(counts)
    stats["total"] = sum(counts.values())
    # Unknown outcomes must fail closed instead of disappearing from the total.
    stats.setdefault("killed", 0)
    for key in (
        "survived",
        "no_tests",
        "suspicious",
        "timeout",
        "segfault",
        "check_was_interrupted_by_user",
    ):
        stats.setdefault(key, 0)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        action="append",
        default=[],
        help="Explicit mutant-name glob; repeat for multiple scopes",
    )
    args, forwarded = parser.parse_known_args()
    stats_path = Path("mutants/mutmut-cicd-stats.json")
    stats_path.unlink(missing_ok=True)
    subprocess.run(
        ["mutmut", "run", *forwarded, *args.scope], check=True, stdout=subprocess.DEVNULL
    )
    subprocess.run(["mutmut", "export-cicd-stats"], check=True, stdout=subprocess.DEVNULL)
    stats = json.loads(stats_path.read_text())
    if args.scope:
        stats = scoped_stats(args.scope)
        Path("mutants/mutmut-scoped-stats.json").write_text(
            json.dumps({"scope": args.scope, **stats}, indent=2) + "\n"
        )
        print(f"Scoped mutation check: {args.scope}")
    failures = (
        "survived",
        "no_tests",
        "suspicious",
        "timeout",
        "segfault",
        "check_was_interrupted_by_user",
    )
    bad = {key: stats[key] for key in failures if stats[key]}
    accounted = stats["killed"] + stats.get("skipped", 0) + sum(bad.values())
    if stats["total"] > accounted:
        bad["not_checked"] = stats["total"] - accounted
    print(f"mutants: {stats['killed']}/{stats['total']} killed")
    if bad or stats["total"] == 0:
        subprocess.run(["mutmut", "results"], check=True)
        print(f"Incomplete mutation validation: {bad or 'no mutants executed'}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
