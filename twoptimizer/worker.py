"""One isolated engine invocation; native solver output cannot corrupt the TUI."""

import json
import sys
import traceback
from pathlib import Path

from twoptimizer.service import RunConfig, solve_case


def main():
    request_path, output_path = map(Path, sys.argv[1:])
    try:
        result = solve_case(RunConfig(**json.loads(request_path.read_text())))
        output_path.write_text(json.dumps(result, allow_nan=False))
        return 0
    except Exception as error:
        output_path.write_text(json.dumps({"error": str(error)}))
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
