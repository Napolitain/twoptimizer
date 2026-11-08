"""Rebuild inspectable public reference facts without executing HoI4 scripts.

The input is an explicitly supplied checkout. No network requests are made.
Optional date/DLC control-flow selection is kept separate from literal facts;
script effects, inheritance and game defaults are not executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from types import MappingProxyType

from games.hoi4.data_pipeline.selection import (
    SelectionContext,
    all_gameplay_context,
    select_history,
)
from games.hoi4.data_pipeline.syntax import (
    Atom,
    Block,
    Document,
    Entry,
    ScriptSyntaxError,
    parse_bytes,
    recover_complete_children,
)
from games.hoi4.planning.time import CampaignDate

REFERENCE_ROOT = Path(__file__).resolve().parents[1] / "data" / "public_reference"
SOURCE_URL = "https://github.com/BanderaModding/vanilla-fin-hoi4"
SOURCE_REVISION = "e249d22284449ece5416b41e68c4d73f2b79e3cc"
COUNTRIES = MappingProxyType(
    {
        "FRA": "France",
        "ENG": "United Kingdom",
        "USA": "United States",
        "GER": "Germany",
        "ITA": "Italy",
        "JAP": "Japan",
        "SOV": "Soviet Union",
        "CHI": "China",
    }
)
SEMANTICS = (
    "Literal source declarations only; not usable capacity or a fully resolved 1936 snapshot. "
    "Base declarations do not apply conditions or dated history. Optional source_selection records "
    "conservative control-flow choices separately. Effects, defaults, inheritance and load order "
    "are not executed. The public mirror's exact game patch and vanilla fidelity are unverified."
)
ECONOMIC_EQUIPMENT_FIELDS = {
    "year",
    "archetype",
    "parent",
    "is_archetype",
    "is_buildable",
    "active",
    "type",
    "build_cost_ic",
    "manpower",
    "reliability",
    "fuel_consumption",
    "priority",
}
TRAINING_UNIT_FIELDS = {"manpower", "training_time", "active", "group", "combat_width"}
PRODUCTION_DEFINES = {
    "MAX_CIV_FACTORIES_PER_LINE",
    "BASE_FACTORY_SPEED",
    "BASE_FACTORY_SPEED_MIL",
    "BASE_FACTORY_SPEED_NAV",
    "POWERED_FACTORY_SPEED",
    "POWERED_FACTORY_SPEED_MIL",
    "POWERED_FACTORY_SPEED_NAV",
    "BASE_FACTORY_START_EFFICIENCY_FACTOR",
    "BASE_FACTORY_MAX_EFFICIENCY_FACTOR",
    "BASE_FACTORY_EFFICIENCY_GAIN",
    "BASE_FACTORY_EFFICIENCY_BALANCE_FACTOR",
    "INFRA_MAX_CONSTRUCTION_COST_EFFECT",
    "MIN_POSSIBLE_TRAINING_MANPOWER",
    "MIN_FIELD_TO_TRAINING_MANPOWER_RATIO",
    "BASE_DEPLOYMENT_TRAINING",
    "RESOURCE_TO_ENERGY_COEFFICIENT",
    "BASE_COUNTRY_ENERGY_PRODUCTION",
    "ENERGY_SCALING_COST_BY_FACTORY_COUNT",
    "BASE_ENERGY_COST",
    "ENERGY_COST_CAP",
    "ENERGY_SCALE_PER_TRADE_FACTORY_EXPORT",
    "PRODUCTION_RESOURCE_LACK_PENALTY",
    "MIN_DIVISION_DEPLOYMENT_TRAINING",
}


def _source(path: Path, root: Path) -> dict:
    payload = path.read_bytes()
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
    }


class SourceInputs:
    """Read pinned source documents while preserving hashes and partial-source diagnostics."""

    def __init__(self, root: Path, context: SelectionContext | None = None):
        self.root = root
        self.context = context
        self.sources: dict[str, dict] = {}
        self.diagnostics: list[dict] = []
        self.partial_effects: dict[str, tuple[Entry, ...]] = {}

    def document(self, path: Path, *, allow_prefix: bool = False) -> Document:
        source = _source(path, self.root)
        self.sources[source["path"]] = source
        payload = path.read_bytes()
        try:
            return parse_bytes(payload, source=source["path"])
        except ScriptSyntaxError as error:
            if not allow_prefix or "Unclosed block" not in str(error):
                raise
            text = payload.decode("utf-8")
            statement_start = text.rfind("\n", 0, error.offset) + 1
            prefix = parse_bytes(text[:statement_start].encode("utf-8"), source=source["path"])
            self.diagnostics.append(
                {
                    "path": source["path"],
                    "error": str(error),
                    "status": "balanced_top_level_prefix_only",
                    "excluded_from_line": error.line,
                }
            )
            self._recover_effect_children(text, error, source["path"], statement_start)
            return Document(source["path"], text, source["sha256"], prefix.root)

    def _recover_effect_children(self, text, error, source, statement_start):
        header = text[statement_start : error.offset]
        if re.fullmatch(r"\s*instant_effect\s*=\s*", header) is None:
            return
        recovery = recover_complete_children(text, error.offset, source=source)
        self.partial_effects[source] = recovery.entries
        diagnostic = self.diagnostics[-1]
        diagnostic["status"] = "balanced_children_of_incomplete_parent"
        diagnostic["unclosed_parent_line"] = diagnostic.pop("excluded_from_line")
        diagnostic["recovered_complete_children"] = len(recovery.entries)
        diagnostic["child_recovery_error"] = str(recovery.error) if recovery.error else None

    def reference(self, document: Document) -> dict:
        return self.sources[document.source]


def _line(document: Document, entry: Entry | Block) -> int:
    return document.position(entry.span.start)[0]


def _blocks(block: Block, field: str) -> tuple[Block, ...]:
    return tuple(value for value in block.assignments(field) if isinstance(value, Block))


def _one_literal(block: Block, field: str):
    values = block.assignments(field)
    return values[0].literal() if len(values) == 1 and isinstance(values[0], Atom) else None


def _literal_record(document: Document, entry: Entry) -> dict:
    assert isinstance(entry.value, Atom)
    return {"field": entry.name, "value": entry.value.literal(), "line": _line(document, entry)}


def _literal_declarations(document: Document, block: Block, fields: set[str] | None = None):
    return [
        _literal_record(document, entry)
        for entry in block.entries
        if entry.operator == "="
        and isinstance(entry.value, Atom)
        and (fields is None or entry.name in fields)
    ]


def _unresolved(document: Document, block: Block, handled: set[str] | None = None):
    return [
        {"field": entry.name, "operator": entry.operator, "line": _line(document, entry)}
        for entry in block.entries
        if not (entry.operator == "=" and isinstance(entry.value, Atom))
        and entry.name not in (handled or set())
    ]


def _flat_blocks(document: Document, block: Block, field: str):
    return [
        {
            "line": _line(document, child),
            "declarations": _literal_declarations(document, child),
            "unresolved_statements": _unresolved(document, child),
        }
        for child in _blocks(block, field)
    ]


def _state_record(document: Document, state: Block, history: Block, inputs: SourceInputs):
    return {
        "id": _one_literal(state, "id"),
        "name_key": _one_literal(state, "name"),
        "category": _one_literal(state, "state_category"),
        "manpower": _one_literal(state, "manpower"),
        "source": inputs.reference(document),
        "history_declarations": _literal_declarations(document, history),
        "base_building_blocks": _flat_blocks(document, history, "buildings"),
        "resource_blocks": _flat_blocks(document, state, "resources"),
        "unresolved_history_statements": _unresolved(document, history, {"buildings"}),
        "unresolved_state_statements": _unresolved(document, state, {"history", "resources"}),
    }


def _states(inputs: SourceInputs):
    result: dict[str, list] = {tag: [] for tag in COUNTRIES}
    unknown = []
    for path in sorted((inputs.root / "history" / "states").glob("*.txt")):
        document = inputs.document(path)
        for state in _blocks(document.root, "state"):
            histories = _blocks(state, "history")
            owner = _one_literal(histories[0], "owner") if len(histories) == 1 else None
            if owner is None:
                unknown.append(
                    {"path": document.source, "reason": "ambiguous or absent base owner"}
                )
            elif owner in result:
                result[owner].append(_state_record(document, state, histories[0], inputs))
    return result, unknown


def _template_record(document: Document, template: Block):
    groups = {}
    for field in ("regiments", "support"):
        groups[field] = [
            {
                "unit": entry.name,
                "line": _line(document, entry),
                "position_declarations": _literal_declarations(document, entry.value),
            }
            for block in _blocks(template, field)
            for entry in block.entries
            if entry.operator == "=" and isinstance(entry.value, Block)
        ]
    return {
        "name": _one_literal(template, "name"),
        "line": _line(document, template),
        "declarations": _literal_declarations(document, template),
        **groups,
        "unresolved_statements": _unresolved(document, template, {"regiments", "support"}),
    }


def _production_record(document: Document, production: Block):
    return {
        "line": _line(document, production),
        "declarations": _literal_declarations(document, production),
        "equipment_blocks": _flat_blocks(document, production, "equipment"),
        "unresolved_statements": _unresolved(document, production, {"equipment"}),
    }


def _production_records(document: Document, incomplete_children: tuple[Entry, ...] = ()):
    records = [
        _production_record(document, production)
        for effects in _blocks(document.root, "instant_effect")
        for production in _blocks(effects, "add_equipment_production")
    ]
    records.extend(
        {**_production_record(document, entry.value), "parent_incomplete": True}
        for entry in incomplete_children
        if entry.name == "add_equipment_production" and isinstance(entry.value, Block)
    )
    return records


def _oob_records(inputs: SourceInputs, tag: str):
    records = []
    for path in sorted((inputs.root / "history" / "units").glob(f"{tag}_1936*.txt")):
        document = inputs.document(path, allow_prefix=True)
        records.append(
            {
                "source": inputs.reference(document),
                "branch_selected": False,
                "parse_diagnostics": [
                    row for row in inputs.diagnostics if row["path"] == document.source
                ],
                "templates": [
                    _template_record(document, block)
                    for block in _blocks(document.root, "division_template")
                ],
                "production_lines": _production_records(
                    document, inputs.partial_effects.get(document.source, ())
                ),
                "unresolved_statements": _unresolved(
                    document, document.root, {"division_template"}
                ),
            }
        )
    return records


def _state_building_values(state: dict):
    result: dict[str, list] = {}
    for block in state["base_building_blocks"]:
        for row in block["declarations"]:
            if row["field"] in {"industrial_complex", "arms_factory", "dockyard"}:
                result.setdefault(row["field"], []).append(row["value"])
    return result


def _totals(states: list):
    totals: Counter = Counter()
    ambiguous = set()
    for state in states:
        for field, values in _state_building_values(state).items():
            if len(values) != 1 or not isinstance(values[0], int) or isinstance(values[0], bool):
                ambiguous.add(field)
            else:
                totals[field] += values[0]
    for field in ambiguous:
        totals.pop(field, None)
    return {"state_count": len(states), **dict(totals)}


def _country(inputs: SourceInputs, tag: str, states: list):
    paths = sorted((inputs.root / "history" / "countries").glob(f"{tag} - *.txt"))
    if len(paths) != 1:
        raise ValueError(f"Expected one country history for {tag}; found {len(paths)}")
    document = inputs.document(paths[0])
    result = {
        "schema_version": 1,
        "tag": tag,
        "name": COUNTRIES[tag],
        "semantics": SEMANTICS,
        "source_revision": SOURCE_REVISION,
        "source_repository": SOURCE_URL,
        "source": inputs.reference(document),
        "country_declarations": _literal_declarations(document, document.root),
        "unresolved_country_statements": _unresolved(document, document.root),
        "states": states,
        "literal_state_totals": _totals(states),
        "oob_candidates": _oob_records(inputs, tag),
    }
    if inputs.context is not None:
        result["source_selection"] = _selected_country_context(document, inputs.context)
    return result


def _selected_country_context(document: Document, context: SelectionContext):
    selection = select_history(document, context)
    block = Block(selection.entries, document.root.span)
    scalars = _literal_declarations(document, block)
    return {
        "start": context.start.to_dict(),
        "enabled_gameplay_dlc": sorted(context.enabled_dlcs),
        "semantics": "Selected source candidates only; game effects are not executed.",
        "candidate_scalars": scalars,
        "oob_references": [
            row
            for row in scalars
            if row["field"] in {"oob", "set_oob", "set_air_oob", "set_naval_oob"}
        ],
        "technology_blocks": _flat_blocks(document, block, "set_technology"),
        "idea_operations": [
            {
                "operation": entry.name,
                "line": _line(document, entry),
                "identifiers": [
                    child.value.text
                    for child in entry.value.entries
                    if child.name is None and isinstance(child.value, Atom)
                ],
                "unresolved_statements": _unresolved(document, entry.value),
            }
            for entry in selection.entries
            if entry.name in {"add_ideas", "remove_ideas"} and isinstance(entry.value, Block)
        ],
        "blockers": [
            {"code": issue.code, "field": issue.field, "line": document.position(issue.offset)[0]}
            for issue in selection.blockers
        ],
        "decisions": [
            {
                "field": decision.field,
                "outcome": decision.outcome.value,
                "line": document.position(decision.offset)[0],
            }
            for decision in selection.decisions
        ],
        "unexecuted_statements": [
            {"field": entry.name, "line": _line(document, entry)} for entry in selection.entries
        ],
        "fully_resolved_country": False,
    }


def _definition_records(inputs: SourceInputs, paths, container: str, fields=None, nested=()):
    result = []
    for path in sorted(paths):
        document = inputs.document(path)
        for body in _blocks(document.root, container):
            for entry in body.entries:
                if entry.operator != "=" or not isinstance(entry.value, Block):
                    continue
                result.append(
                    {
                        "id": entry.name,
                        "source": inputs.reference(document),
                        "line": _line(document, entry),
                        "declarations": _literal_declarations(document, entry.value, fields),
                        **{field: _flat_blocks(document, entry.value, field) for field in nested},
                        "unresolved_statements": _unresolved(document, entry.value, set(nested)),
                    }
                )
    return result


def _equipment(inputs: SourceInputs):
    root = inputs.root / "common" / "units"
    return {
        "schema_version": 1,
        "semantics": SEMANTICS,
        "source_revision": SOURCE_REVISION,
        "source_repository": SOURCE_URL,
        "equipment": _definition_records(
            inputs,
            (root / "equipment").glob("*.txt"),
            "equipments",
            ECONOMIC_EQUIPMENT_FIELDS,
            ("resources",),
        ),
        "duplicate_archetypes": _definition_records(
            inputs,
            (root / "equipment").glob("*.txt"),
            "duplicate_archetypes",
            ECONOMIC_EQUIPMENT_FIELDS,
            ("resources",),
        ),
        "units": _definition_records(
            inputs, root.glob("*.txt"), "sub_units", TRAINING_UNIT_FIELDS, ("need",)
        ),
    }


def _numeric_defines(inputs: SourceInputs):
    path = inputs.root / "common" / "defines" / "00_defines.lua"
    source = _source(path, inputs.root)
    inputs.sources[source["path"]] = source
    rows = []
    pattern = re.compile(r"\s*(\w+)\s*=\s*(-?\d+(?:\.\d+)?)\s*,")
    for line, text in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        match = pattern.fullmatch(text.split("--", 1)[0].rstrip())
        if match and match[1] in PRODUCTION_DEFINES:
            rows.append({"field": match[1], "value": json.loads(match[2]), "line": line})
    return {
        "source": source,
        "declarations": rows,
        "semantics": "Selected literal assignments only; Lua is not executed.",
    }


def _building_rules(inputs: SourceInputs):
    root = inputs.root / "common"
    return {
        "schema_version": 1,
        "semantics": SEMANTICS,
        "source_revision": SOURCE_REVISION,
        "source_repository": SOURCE_URL,
        "buildings": _definition_records(
            inputs, (root / "buildings").glob("*.txt"), "buildings", nested=("level_cap",)
        ),
        "state_categories": _definition_records(
            inputs, (root / "state_category").glob("*.txt"), "state_categories"
        ),
        "numeric_defines": _numeric_defines(inputs),
    }


def _write(path: Path, payload: dict):
    content = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(content) >= 500 * 1024:
        content = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
    if len(content) >= 500 * 1024:
        raise ValueError(f"Reference output exceeds 500 KiB: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {"path": path.name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def verify_source_checkout(root: Path):
    """Do not label arbitrary local edits as the pinned public repository revision."""
    revision = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if revision != SOURCE_REVISION:
        raise ValueError(f"Expected public source revision {SOURCE_REVISION}, found {revision}")
    changes = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            "common",
            "history",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if changes:
        raise ValueError("Public source checkout has changed or untracked common/history files")


def build_public_reference(
    source_root: Path | str,
    output_root: Path | str,
    *,
    inspection_start: CampaignDate | None = None,
    dlc_catalog_path: Path | str | None = None,
) -> dict:
    """Extract source literals; the caller supplies the pinned checkout explicitly."""
    if (inspection_start is None) != (dlc_catalog_path is None):
        raise ValueError("Provide both an inspection start and a sourced DLC catalog")
    context = (
        all_gameplay_context(inspection_start, dlc_catalog_path)
        if inspection_start is not None and dlc_catalog_path is not None
        else None
    )
    inputs = SourceInputs(Path(source_root), context)
    output = Path(output_root)
    if not (inputs.root / "history" / "states").is_dir():
        raise ValueError("Expected a game-source directory containing history/states")
    verify_source_checkout(inputs.root)
    states, unresolved_owners = _states(inputs)
    artifacts, countries = [], []
    for tag, owned_states in states.items():
        country = _country(inputs, tag, owned_states)
        artifact = _write(output / "countries" / f"{tag}.json", country)
        artifact["path"] = f"countries/{tag}.json"
        artifacts.append(artifact)
        countries.append(
            {
                "tag": tag,
                "name": COUNTRIES[tag],
                "literal_state_totals": country["literal_state_totals"],
            }
        )
    equipment, buildings = _equipment(inputs), _building_rules(inputs)
    artifacts.append(_write(output / "equipment.json", equipment))
    artifacts.append(_write(output / "building_rules.json", buildings))
    manifest = {
        "schema_version": 1,
        "semantics": SEMANTICS,
        "source": {
            "repository": SOURCE_URL,
            "revision": SOURCE_REVISION,
            "revision_date": "2026-08-20T21:45:23Z",
            "retrieved_at_utc": "2026-11-08",
            "game_patch": None,
            "vanilla_validated": False,
            "dlc_selection": None,
            "license": "No repository license declared; factual declarations extracted only",
            "version_evidence": (
                "00_defines.lua SAVE_VERSION=33; comment says "
                "1.17.0 (Case Green), which is internally inconsistent"
            ),
        },
        "requested_target": {
            "policy": "latest stable game version",
            "version": "1.19.4",
            "checksum": "0bdb",
            "latest_hotfix_date": "2026-11-05",
            "checked_at": "2026-11-08",
            "source": "https://steamcommunity.com/ogg/394360/announcements/detail/684142629662760620",
            "reference_validated_against_target": False,
        },
        "requested_ruleset": {
            "game_version_policy": "latest_stable",
            "gameplay_dlc_policy": "all_enabled",
            "confirmed_by_user": True,
            "source_branches_resolved": False,
            "country_history_control_flow_inspected": context is not None,
            "reference_validated_against_ruleset": False,
        },
        "supplementary_rules_evidence": "rules_evidence.json",
        "rebuild_command": (
            "uv run --frozen python -m games.hoi4.data_pipeline.public_import "
            "--source-root /path/to/pinned-checkout "
            "--output games/hoi4/data/public_reference"
        ),
        "countries": countries,
        "unresolved_state_owners": unresolved_owners,
        "source_diagnostics": inputs.diagnostics,
        "coverage": {
            "country_profiles": len(countries),
            "state_files_examined": sum(s.startswith("history/states/") for s in inputs.sources),
            "owned_state_records": sum(len(rows) for rows in states.values()),
            "equipment_records": len(equipment["equipment"]),
            "duplicate_archetype_records": len(equipment["duplicate_archetypes"]),
            "unit_records": len(equipment["units"]),
            "building_records": len(buildings["buildings"]),
            "state_category_records": len(buildings["state_categories"]),
            "numeric_defines": len(buildings["numeric_defines"]["declarations"]),
            "executed_effects": 0,
            "validated_scenarios": 0,
        },
        "input_sources": [inputs.sources[path] for path in sorted(inputs.sources)],
        "artifacts": artifacts,
    }
    if dlc_catalog_path is not None:
        path = Path(dlc_catalog_path)
        manifest["selection_catalog"] = _source(path, path.parent)
        manifest["rebuild_command"] += (
            f" --start {inspection_start} "
            "--dlc-catalog games/hoi4/data/public_reference/dlc_catalog.json"
        )
    _write(output / "manifest.json", manifest)
    return manifest


def load_reference_manifest(root: Path | str = REFERENCE_ROOT) -> dict:
    return json.loads((Path(root) / "manifest.json").read_text(encoding="utf-8"))


def load_reference_equipment(root: Path | str = REFERENCE_ROOT) -> dict:
    return json.loads((Path(root) / "equipment.json").read_text(encoding="utf-8"))


def load_reference_country(tag: str, root: Path | str = REFERENCE_ROOT) -> dict:
    normalized = tag.upper()
    if normalized not in COUNTRIES:
        raise ValueError(f"Unknown reference country {tag!r}; choose {', '.join(COUNTRIES)}")
    return json.loads((Path(root) / "countries" / f"{normalized}.json").read_text(encoding="utf-8"))


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--start", default="1936.1.1.12", type=CampaignDate.parse)
    parser.add_argument("--dlc-catalog", type=Path, default=REFERENCE_ROOT / "dlc_catalog.json")
    args = parser.parse_args(argv)
    manifest = build_public_reference(
        args.source_root,
        args.output,
        inspection_start=args.start,
        dlc_catalog_path=args.dlc_catalog,
    )
    print(json.dumps(manifest["coverage"], indent=2))


if __name__ == "__main__":
    main()
