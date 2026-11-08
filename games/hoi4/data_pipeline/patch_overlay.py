"""Guarded release-note corrections to specific imported fields, never a version stamp."""

import json
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path

from games.hoi4.data_pipeline.public_import import REFERENCE_ROOT


def load_patch_overlays(root: Path | str = REFERENCE_ROOT) -> dict:
    """Return caller-owned sourced corrections; loading does not change reference files."""
    return json.loads((Path(root) / "patch_overlays.json").read_text(encoding="utf-8"))


def _declarations(record: dict, block: str | None, field: str) -> list[dict]:
    groups = [record] if block is None else record.get(block, [])
    return [
        declaration
        for group in groups
        for declaration in group.get("declarations", [])
        if declaration["field"] == field
    ]


def _matching_record(payload: dict, correction: dict) -> tuple[dict | None, str | None]:
    records = [
        row
        for row in payload.get(correction["section"], [])
        if row["id"] == correction["record_id"]
    ]
    if len(records) != 1:
        return None, "missing_record" if not records else "ambiguous_record"
    record = records[0]
    if record.get("source", {}).get("path") != correction["raw_source_path"]:
        return None, "source_path_mismatch"
    return record, None


def _correct_field(payload: dict, correction: dict, source: dict, target: dict) -> dict:
    evidence = {**deepcopy(correction), "release_source": deepcopy(source)}
    record, status = _matching_record(payload, correction)
    if record is None:
        return {**evidence, "status": status, "target_field_supported": False}
    rows = _declarations(record, correction["block"], correction["field"])
    evidence["raw_source"] = deepcopy(record["source"])
    if len(rows) != 1:
        status = "missing_field" if not rows else "ambiguous_field"
        return {**evidence, "status": status, "target_field_supported": False}
    row = rows[0]
    value = row["value"]
    evidence.update(observed_value=value, line=row.get("line"))
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        status = "nonnumeric_field"
    elif value == correction["new_value"]:
        status = "already_target_value"
    elif value == correction["old_value"]:
        status = "applied"
    else:
        status = "value_mismatch"
    supported = status in {"applied", "already_target_value"}
    evidence.update(status=status, target_field_supported=supported)
    if status == "applied":
        row["value"] = correction["new_value"]
    _record_evidence(row, evidence, target)
    return evidence


def _record_evidence(row: dict, evidence: dict, target: dict) -> None:
    previous = row.get("patch_overlay", {})
    unchanged = (
        evidence["status"] == "already_target_value"
        and previous.get("id") == evidence["id"]
        and previous.get("target") == target
        and previous.get("new_value") == evidence["new_value"]
        and previous.get("target_field_supported") is True
    )
    if not unchanged:
        row["patch_overlay"] = {**deepcopy(evidence), "target": deepcopy(target)}


def apply_patch_overlays(inputs: Mapping, manifest: Mapping | None = None) -> tuple[dict, dict]:
    """Copy inputs and apply only unique, source-matched, old-or-new guarded fields.

    Mismatches retain the original declarations and appear as unresolved diagnostics.
    Consumers must not treat those retained values as validated for the target patch.
    The field's raw source/hash remains its origin; ``patch_overlay`` gives the
    release evidence for a corrected value. Reapplying never changes a value twice.
    """
    manifest = load_patch_overlays() if manifest is None else manifest
    patched = deepcopy(dict(inputs))
    fields = [
        _correct_field(
            patched, correction, manifest["sources"][correction["release"]], manifest["target"]
        )
        for correction in manifest["corrections"]
    ]
    report = {
        "schema_version": 1,
        "target": deepcopy(manifest["target"]),
        "scope": "Only listed fields are supported by patch notes; no full dataset validation.",
        "identifier_evidence": deepcopy(manifest["identifier_evidence"]),
        "full_version_validated": False,
        "runnable_scenario_established": False,
        "counts": dict(Counter(field["status"] for field in fields)),
        "fields": fields,
        "unresolved": [field for field in fields if not field["target_field_supported"]],
    }
    patched["semantics"] = (
        "Caller-owned source declarations with guarded release-note field corrections. "
        "Source hashes identify original raw files; patch_overlay records correction evidence. "
        "Uncovered and conflicting fields are not validated against the target game version."
    )
    return patched, report
