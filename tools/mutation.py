"""Run mutation testing and reject incomplete or surviving results."""

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    stats_path = Path("mutants/mutmut-cicd-stats.json")
    stats_path.unlink(missing_ok=True)
    subprocess.run(["mutmut", "run", *sys.argv[1:]], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["mutmut", "export-cicd-stats"], check=True, stdout=subprocess.DEVNULL)
    stats = json.loads(stats_path.read_text())
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
