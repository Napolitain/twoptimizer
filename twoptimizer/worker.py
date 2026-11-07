"""One isolated engine invocation; native solver output cannot corrupt the TUI."""

import json
import sys
import traceback
from pathlib import Path

from twoptimizer.progress import PREFIX
from twoptimizer.service import RunConfig, solve_case


def main():
    request_path, output_path = map(Path, sys.argv[1:])
    try:

        def progress(phase):
            print(PREFIX + json.dumps({"phase": phase}), flush=True)

        result = solve_case(
            RunConfig(**json.loads(request_path.read_text())), progress=progress
        )
        output_path.write_text(json.dumps(result, allow_nan=False))
        return 0
    except Exception as error:  # noqa: BLE001 -- report any engine failure across the process boundary
        output_path.write_text(json.dumps({"error": str(error)}))
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
