"""Build reproducible, partial scenario data from independently resolved source systems.

This supplements the literal reference. A resolved equipment cost, army template
or national modifier does not certify an executable latest-patch campaign.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path

from games.hoi4.data_pipeline import public_import
from games.hoi4.data_pipeline.equipment_resolution import (
    resolve_equipment_catalog,
    resolve_equipment_variant,
)
from games.hoi4.data_pipeline.equipment_sources import read_equipment_resolution_inputs
from games.hoi4.data_pipeline.modifier_resolution import (
    load_modifier_catalog,
    resolve_country_modifiers,
    resolve_support_profile,
)
from games.hoi4.data_pipeline.oob_resolution import resolve_starting_army
from games.hoi4.data_pipeline.patch_overlay import apply_patch_overlays, load_patch_overlays
from games.hoi4.data_pipeline.selection import all_gameplay_context
from games.hoi4.data_pipeline.state_economy import (
    read_state_economy_inputs,
    summarize_country_states,
)
from games.hoi4.planning.time import CampaignDate

DERIVED_ROOT = public_import.REFERENCE_ROOT / "derived"
MAX_ARTIFACT_BYTES = 450 * 1024
DEFAULT_START = CampaignDate(1936, 1, 1, 12)


def _encoded(payload) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")


def _fingerprint(path: Path, relative: str) -> dict:
    content = path.read_bytes()
    return {"path": relative, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def _write(root: Path, relative: str, payload) -> dict:
    content = _encoded(payload)
    if len(content) >= 500 * 1024:
        raise ValueError(f"Derived reference artifact exceeds 500 KiB: {relative}")
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {"path": relative, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def _checked_artifact(root: Path, artifact: dict):
    relative = Path(artifact["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Reference artifact path must stay inside its catalog")
    path = root / relative
    if _fingerprint(path, relative.as_posix()) != artifact:
        raise ValueError(f"Reference artifact checksum mismatch: {relative}")
    return json.loads(path.read_text(encoding="utf-8"))


def _equipment_parts(root: Path, records: list[dict], prefix: str = "equipment") -> list[dict]:
    parts, chunk = [], []
    size = 2
    for record in records:
        record_size = len(_encoded(record)) + 1
        if chunk and size + record_size > MAX_ARTIFACT_BYTES:
            parts.append(_write(root, f"{prefix}/part-{len(parts):03d}.json", chunk))
            chunk, size = [], 2
        chunk.append(record)
        size += record_size
    if chunk:
        parts.append(_write(root, f"{prefix}/part-{len(parts):03d}.json", chunk))
    return parts


def _public_artifacts(root: Path, manifest: dict) -> dict:
    artifacts = {row["path"]: row for row in manifest["artifacts"]}
    paths = [
        "equipment.json",
        "building_rules.json",
        *(f"countries/{tag}.json" for tag in public_import.COUNTRIES),
    ]
    return {name: _checked_artifact(root, artifacts[name]) for name in paths}


def _country_documents(reader: public_import.SourceInputs, profile: dict):
    country = reader.document(reader.root / profile["source"]["path"])
    oobs = {
        Path(candidate["source"]["path"]).stem: reader.document(
            reader.root / candidate["source"]["path"], allow_prefix=True
        )
        for candidate in profile["oob_candidates"]
    }
    return country, oobs


def _source_union(*groups) -> list[dict]:
    result = {}
    for group in groups:
        for source in group:
            previous = result.setdefault(source["path"], source)
            if previous != source:
                raise ValueError(f"Conflicting input source fingerprints: {source['path']}")
    return [result[key] for key in sorted(result)]


def build_resolved_reference(
    source_root: Path | str,
    output_root: Path | str = DERIVED_ROOT,
    *,
    reference_root: Path | str = public_import.REFERENCE_ROOT,
    start: CampaignDate = DEFAULT_START,
) -> dict:
    """Interpret supported source semantics; retain every subsystem's limitations."""
    source_root, output, reference = Path(source_root), Path(output_root), Path(reference_root)
    if output.resolve() == reference.resolve():
        raise ValueError("Derived output must not overwrite the literal reference")
    public_import.verify_source_checkout(source_root)
    source_manifest = public_import.load_reference_manifest(reference)
    if source_manifest["source"]["revision"] != public_import.SOURCE_REVISION:
        raise ValueError("Literal reference and requested source revision differ")
    base = _public_artifacts(reference, source_manifest)
    context = replace(all_gameplay_context(start, reference / "dlc_catalog.json"), tutorial=False)
    reader = public_import.SourceInputs(source_root, context)
    raw_equipment = read_equipment_resolution_inputs(source_root)
    raw_equipment.update(
        units=base["equipment.json"]["units"],
        source_repository=source_manifest["source"]["repository"],
        source_revision=source_manifest["source"]["revision"],
    )
    equipment, patches = apply_patch_overlays(raw_equipment, load_patch_overlays(reference))
    resolved_equipment = resolve_equipment_catalog(equipment)
    catalog = load_modifier_catalog(source_root)
    artifacts = [*_equipment_parts(output, resolved_equipment["equipment"])]
    artifacts.append(
        _write(
            output,
            "equipment-summary.json",
            {key: value for key, value in resolved_equipment.items() if key != "equipment"},
        )
    )
    artifacts.append(_write(output, "patch-report.json", patches))
    artifacts.append(_write(output, "support-profile.json", resolve_support_profile(catalog)))
    countries, state_sources = [], []
    for tag in public_import.COUNTRIES:
        profile = base[f"countries/{tag}.json"]
        document, oobs = _country_documents(reader, profile)
        army = resolve_starting_army(
            profile,
            equipment,
            document,
            oobs,
            context,
            partial_effects=reader.partial_effects,
            tutorial=False,
        )
        modifiers = resolve_country_modifiers(document, context, catalog, tag=tag)
        supplements = read_state_economy_inputs(source_root, profile)
        states = summarize_country_states(
            profile, base["building_rules.json"], supplements=supplements, context=context
        )
        state_sources.extend(supplements["input_sources"])
        variants = [
            resolve_equipment_variant(
                resolved_equipment,
                variant,
                module_records=equipment["modules"],
                upgrade_records=equipment["upgrades"],
            )
            for variant in army["variants"]
        ]
        artifacts.append(_write(output, f"armies/{tag}.json", army))
        artifacts.append(_write(output, f"modifiers/{tag}.json", modifiers))
        artifacts.append(_write(output, f"states/{tag}.json", states))
        artifacts.extend(_equipment_parts(output, variants, f"variants/{tag}"))
        countries.append(
            {
                "tag": tag,
                "army": army["summary"],
                "selected_modifier_contributions": len(modifiers["contributions"]),
                "selected_modifier_blockers": len(modifiers["blockers"]),
                "state_totals": states["totals"],
                "named_variants": len(variants),
                "resolved_variant_base": sum(
                    variant["status"] == "resolved_variant_base" for variant in variants
                ),
                "scenario_ready": False,
            }
        )
    manifest = {
        "schema_version": 1,
        "kind": "partial_scenario_reference",
        "source": source_manifest["source"],
        "target": source_manifest["requested_target"],
        "start": start.to_dict(),
        "tutorial": False,
        "enabled_gameplay_dlc": sorted(context.enabled_dlcs),
        "full_version_validated": False,
        "scenario_ready": False,
        "scope": (
            "Supported source rules only; subsystem unknowns remain explicit. "
            "No campaign feasibility proof."
        ),
        "reference_inputs": [
            _fingerprint(reference / path, path)
            for path in ("manifest.json", "dlc_catalog.json", "patch_overlays.json")
        ],
        "input_sources": _source_union(
            source_manifest["input_sources"],
            raw_equipment["input_sources"],
            catalog.input_sources,
            reader.sources.values(),
            state_sources,
        ),
        "source_diagnostics": reader.diagnostics,
        "equipment_counts": resolved_equipment["counts"],
        "patch_counts": patches["counts"],
        "countries": countries,
        "artifacts": artifacts,
    }
    _write(output, "manifest.json", manifest)
    return manifest


def load_resolved_manifest(root: Path | str = DERIVED_ROOT) -> dict:
    return json.loads((Path(root) / "manifest.json").read_text(encoding="utf-8"))


def load_resolved_country(tag: str, root: Path | str = DERIVED_ROOT) -> dict:
    tag = tag.upper()
    if tag not in public_import.COUNTRIES:
        raise ValueError(f"Unknown HoI4 country: {tag}")
    root = Path(root)
    manifest = load_resolved_manifest(root)
    index = {row["path"]: row for row in manifest["artifacts"]}
    return {
        "country": tag,
        "scenario_ready": False,
        "army": _checked_artifact(root, index[f"armies/{tag}.json"]),
        "modifiers": _checked_artifact(root, index[f"modifiers/{tag}.json"]),
        "states": _checked_artifact(root, index[f"states/{tag}.json"]),
        "variants": [
            record
            for name in sorted(index)
            if name.startswith(f"variants/{tag}/")
            for record in _checked_artifact(root, index[name])
        ],
    }


def load_resolved_equipment(root: Path | str = DERIVED_ROOT) -> dict:
    root = Path(root)
    manifest = load_resolved_manifest(root)
    index = {row["path"]: row for row in manifest["artifacts"]}
    summary = _checked_artifact(root, index["equipment-summary.json"])
    summary["equipment"] = [
        record
        for name in sorted(index)
        if name.startswith("equipment/")
        for record in _checked_artifact(root, index[name])
    ]
    return summary


def load_resolved_support_profile(root: Path | str = DERIVED_ROOT) -> dict:
    """Return source endpoint tables, without inferring current country support levels."""
    root = Path(root)
    manifest = load_resolved_manifest(root)
    artifact = next(row for row in manifest["artifacts"] if row["path"] == "support-profile.json")
    return _checked_artifact(root, artifact)


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--reference", type=Path, default=public_import.REFERENCE_ROOT)
    parser.add_argument("--output", type=Path, default=DERIVED_ROOT)
    parser.add_argument(
        "--start",
        type=CampaignDate.parse,
        default="1936.1.1.12",
        help="Selection date; bundled OOB coverage is limited to 1936 candidates",
    )
    args = parser.parse_args(argv)
    manifest = build_resolved_reference(
        args.source_root, args.output, reference_root=args.reference, start=args.start
    )
    print(
        json.dumps(
            {"equipment": manifest["equipment_counts"], "countries": manifest["countries"]},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
