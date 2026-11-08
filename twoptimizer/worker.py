"""One isolated engine invocation; native solver output cannot corrupt the TUI."""

import json
import sys
import traceback
from pathlib import Path

from twoptimizer.errors import serialize_error
from twoptimizer.models import RunConfig
from twoptimizer.progress import PREFIX
from twoptimizer.service import solve_case


def main():
    request_path, output_path = map(Path, sys.argv[1:])
    try:

        def progress(phase):
            print(PREFIX + json.dumps({"phase": phase}), flush=True)

        result = solve_case(
            RunConfig.from_dict(json.loads(request_path.read_text())), progress=progress
        )
        output_path.write_text(json.dumps(result.to_dict(), allow_nan=False))
        return 0
    except Exception as error:
        output_path.write_text(json.dumps(serialize_error(error)))
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
