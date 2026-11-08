"""Console error presentation; application validation stays in the case service."""

import sys
from collections.abc import Callable
from typing import Any

from twoptimizer.errors import ApplicationError


def run_cli(command: Callable[..., Any], argv: list[str] | None = None) -> int:
    try:
        command(argv)
    except ApplicationError as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0
