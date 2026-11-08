"""Isolated engine cases, optionally sharing imports in a sequential batch."""

import json
import sys
import traceback
from pathlib import Path

from games.tw.cancellation import Cancellation
from twoptimizer.errors import serialize_error
from twoptimizer.models import RunConfig
from twoptimizer.progress import PREFIX, encode_progress
from twoptimizer.service import solve_case


def emit(record):
    # Native libraries may leave an unterminated stdout fragment before a frame.
    print("\n" + PREFIX + json.dumps(record), flush=True)


def run_case(request_path: Path, output_path: Path, cancel_path: Path | None = None) -> int:
    """Write one complete result atomically, without retaining model/session state."""
    try:

        def progress(event):
            emit(encode_progress(event))

        config = RunConfig.from_dict(json.loads(request_path.read_text()))
        if cancel_path is None:
            result = solve_case(config, progress=progress)
        else:
            result = solve_case(
                config, progress=progress, cancellation=Cancellation(checker=cancel_path.exists)
            )
        payload = json.dumps(result.to_dict(), allow_nan=False)
        status = 0
    except Exception as error:
        payload = json.dumps(serialize_error(error))
        traceback.print_exc()
        status = 1
    temporary = output_path.with_suffix(".tmp")
    temporary.write_text(payload)
    temporary.replace(output_path)
    return status


def batch_main() -> int:
    """A completed case may fail; malformed transport ends the worker."""
    for line in sys.stdin:
        request = json.loads(line)
        cancel_path = Path(request["cancel"]) if "cancel" in request else None
        run_case(Path(request["request"]), Path(request["output"]), cancel_path)
        emit({"completed": request["id"]})
    return 0


def main():
    if sys.argv[1:] == ["--batch"]:
        return batch_main()
    return run_case(*map(Path, sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
