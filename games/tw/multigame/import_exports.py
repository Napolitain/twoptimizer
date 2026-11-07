"""Ingest installed-game TSV exports without guessing schemas or merging mods.

All chunks, including duplicate keys and unrecognized tables, are preserved.
This prepares inspectable data; table presence alone does not certify a model.
"""

import argparse
import csv
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

GAMES = ("shogun2", "rome2", "three_kingdoms")
CORE_TABLES = {
    "building_levels",
    "building_chains",
    "building_effects_junction",
    "effects",
}
HEADER_NAMES = {
    "key",
    "building",
    "building_level",
    "level",
    "effect",
    "value",
    "effect_scope",
    "scope",
    "culture",
    "faction",
    "name",
    "id",
    "building_chain",
    "cost",
    "description",
}


def table_name(path):
    for parent in path.parents:
        if parent.name.endswith("_tables"):
            return parent.name.removesuffix("_tables")
    return path.stem.removesuffix("_tables")


def ingest(input_dir, output_dir, game, version, mods=None):
    if game not in GAMES or not isinstance(version, str) or not version.strip():
        raise ValueError("Supply the game and installed game/build version")
    input_dir, output_dir = Path(input_dir).resolve(), Path(output_dir).resolve()
    paths = sorted(input_dir.rglob("*.tsv")) if input_dir.is_dir() else []
    if not paths:
        raise ValueError(
            "No TSV exports found. Binary .pack archives must first be exported with RPFM; they are not TSV files."
        )
    if output_dir == input_dir or input_dir in output_dir.parents:
        raise ValueError(
            "Keep the generated bundle outside the source export directory"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "chunks").mkdir(exist_ok=True)
    tables = {}
    csv.field_size_limit(16 * 1024 * 1024)
    for path in paths:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            prefix = source.read(4)
            source.seek(0)
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        encoding = (
            "utf-16" if prefix.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        )
        identity = digest.hexdigest()
        table = table_name(path.relative_to(input_dir))
        safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", table)
        destination = output_dir / "chunks" / f"{safe_name}-{identity}.jsonl"
        temporary = destination.with_suffix(".tmp")
        columns, metadata, count, width = None, [], 0, None
        with (
            path.open(encoding=encoding, newline="") as source,
            temporary.open("w", encoding="utf-8", newline="\n") as target,
        ):
            for row in csv.reader(source, delimiter="\t", strict=True):
                if not row:
                    continue
                if (
                    count == 0
                    and len(row) == 1
                    and re.match(r"^#[a-zA-Z0-9_]+;", row[0])
                ):
                    metadata.append(row)
                    continue
                if width is None:
                    width = len(row)
                    if HEADER_NAMES.intersection(row):
                        if len(set(row)) != len(row) or any(
                            not name.strip() for name in row
                        ):
                            raise ValueError(f"Ambiguous header in {path.name}")
                        columns = row
                        continue
                if len(row) != width:
                    raise ValueError(
                        f"Inconsistent row width in {path.relative_to(input_dir)}: {len(row)} vs {width}"
                    )
                target.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1
        temporary.replace(destination)
        record = {
            "source_file": str(path.relative_to(input_dir)),
            "source_sha256": identity,
            "source_bytes": path.stat().st_size,
            "encoding": encoding,
            "schema_metadata": metadata,
            "columns": columns,
            "schema_status": "named_columns"
            if columns is not None
            else "headerless_preserved_without_column_guesses",
            "row_count": count,
            "column_count": width,
            "data_file": str(destination.relative_to(output_dir)),
        }
        tables.setdefault(table, {"chunks": [], "row_count": 0})["chunks"].append(
            record
        )
        tables[table]["row_count"] += count
    missing = sorted(CORE_TABLES - tables.keys())
    manifest = {
        "schema_version": 1,
        "game": game,
        "installed_version": version,
        "imported_at_utc": datetime.now(UTC).isoformat(),
        "mods": mods,
        "mod_semantics": "Not supplied"
        if mods is None
        else "Declared names/order only; no automatic base/patch/mod precedence applied",
        "tables": tables,
        "table_count": len(tables),
        "chunk_count": len(paths),
        "row_count": sum(t["row_count"] for t in tables.values()),
        "missing_core_tables": missing,
        "ready_for_full_economy_model": False,
        "next_validation": [
            "Resolve exported table schemas and foreign keys",
            "Confirm base/patch/mod load order and campaign",
            "Validate faction/building availability and slot rules",
            "Join technology, faction, population and scoped effects",
            "Validate against game economy panels before publishing game rankings",
        ],
        "note": "Every source chunk is retained separately. Duplicate keys are not silently deduplicated or merged. Core table presence is not a completeness certificate.",
    }
    temporary = output_dir / "manifest.tmp"
    temporary.write_text(json.dumps(manifest, indent=2) + "\n")
    temporary.replace(output_dir / "manifest.json")
    return manifest


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--game", choices=GAMES, required=True)
    cli.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Directory containing exported TSV tables",
    )
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument(
        "--version",
        required=True,
        help="Installed game version/build, as supplied with the exports",
    )
    status = cli.add_mutually_exclusive_group()
    status.add_argument("--vanilla", action="store_true")
    status.add_argument(
        "--mod", action="append", help="Enabled mods in declared load order; repeatable"
    )
    args = cli.parse_args(argv)
    report = ingest(
        args.input,
        args.output,
        args.game,
        args.version,
        [] if args.vanilla else args.mod,
    )
    print(
        f"Imported {report['table_count']} tables / {report['chunk_count']} chunks / {report['row_count']} rows"
    )
    print(
        "Missing minimal core tables:",
        ", ".join(report["missing_core_tables"])
        or "none; full model validation remains required",
    )
    return report


if __name__ == "__main__":
    main()
