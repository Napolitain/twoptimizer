"""Inspect local HoI4 source exports without downloading or evaluating scripts."""

import argparse
import json
from pathlib import Path

from games.hoi4.data_pipeline.inventory import SourceContext, inventory_sources


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    parser.add_argument("--output", type=Path, help="Write JSON here instead of standard output")
    parser.add_argument("--origin-url")
    parser.add_argument("--revision")
    parser.add_argument("--game-build", help="Use only a version established from the source")
    parser.add_argument("--retrieved-at-utc")
    args = parser.parse_args(argv)
    context = SourceContext(
        origin_url=args.origin_url,
        revision=args.revision,
        game_build=args.game_build,
        retrieved_at_utc=args.retrieved_at_utc,
    )
    try:
        inventory = inventory_sources(args.source_root, context=context)
        output = json.dumps(inventory, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
        if args.output:
            args.output.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
    except (OSError, ValueError) as error:
        parser.exit(2, f"Source inventory failed: {error}\n")
    statuses = inventory["coverage"]["statuses"]
    return 1 if statuses.get("syntax_error") or statuses.get("encoding_error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
