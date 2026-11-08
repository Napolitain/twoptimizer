"""JSON and CSV session export, preserving the public report schema."""

import csv
import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any


def export_session(
    path: str | Path,
    results: Sequence[dict[str, Any]],
    *,
    skipped: Sequence[str] = (),
    overwrite: bool = False,
) -> tuple[Path, Path]:
    path = Path(path).expanduser()
    if path.suffix.lower() not in {"", ".json"}:
        raise ValueError("Choose a JSON filename; a matching CSV is saved alongside it.")
    path = path.with_suffix(".json")
    csv_path = path.with_suffix(".csv")
    if not results:
        raise ValueError("Run an optimization before exporting.")
    if not overwrite and (path.exists() or csv_path.exists()):
        raise FileExistsError(
            "A report already exists. Choose another filename or enable replacement."
        )
    payload = {
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(),
        "scope": (
            "Cases compare independent provinces or explicitly joint holdings; "
            "see each request's joint, provinces and adjacency settings. "
            "Automatic effective borders are recorded in raw.map_context. "
            "No cross-game ranking. OPTIMAL is a "
            "solver proof for the stated model. FEASIBLE keeps an unresolved "
            "bound. Cancelled batches may contain fewer cases than requested."
        ),
        "skipped": list(skipped),
        "cases": results,
    }
    encoded = json.dumps(payload, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded)
    fields = (
        "game",
        "faction",
        "province",
        "research",
        "algorithm",
        "status",
        "income",
        "bound",
        "gap_percent",
        "seconds",
        "fertility",
        "soil",
        "tax",
        "town_wealth",
        "time_limit_seconds",
        "workers",
        "elapsed_seconds",
        "build_seconds",
        "search_seconds",
        "joint",
        "province_ids",
        "adjacency",
        "adjacency_mode",
        "adjacency_directed",
        "constraints",
    )
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in results:
            writer.writerow(
                {
                    **{
                        k: row["request"][k]
                        for k in (
                            "game",
                            "research",
                            "fertility",
                            "soil",
                            "tax",
                            "town_wealth",
                        )
                    },
                    "faction": row["faction"],
                    "province": row["province"],
                    "algorithm": row["solver"]["algorithm"],
                    "status": row["solver"]["status"],
                    "income": row["income"],
                    "bound": row["solver"].get("bound"),
                    "gap_percent": row["gap_percent"],
                    "seconds": row["solver"]["seconds"],
                    "time_limit_seconds": row["request"]["seconds"],
                    "workers": row["solver"].get("workers"),
                    "elapsed_seconds": row.get("timings", {}).get("worker_wall_seconds"),
                    "build_seconds": row.get("timings", {}).get("build_model_seconds"),
                    "search_seconds": row["solver"].get("timings", {}).get("search_seconds"),
                    "joint": row["request"].get("joint", False),
                    "province_ids": ";".join(
                        row["request"].get("provinces") or [row["request"]["province"]]
                    ),
                    "adjacency": json.dumps(
                        row.get("raw", {})
                        .get("map_context", {})
                        .get("borders", row["request"].get("adjacency"))
                    ),
                    "adjacency_mode": row.get("raw", {}).get("map_context", {}).get("mode"),
                    "adjacency_directed": row.get("raw", {}).get("map_context", {}).get("directed"),
                    "constraints": json.dumps(row["request"].get("constraints", {})),
                }
            )
    return path, csv_path
