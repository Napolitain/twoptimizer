"""Report the historical reference's coverage separately from the undated Honga audit."""

import hashlib
import json
from collections import Counter
from pathlib import Path

from games.tw.immutable import thaw
from games.tw.three_kingdoms.catalog import DATA, building_effects, load_data


def audit_reference() -> dict:
    data = load_data()
    honga = Path(__file__).parents[1] / "multigame/data/three_kingdoms_details.json"
    old = json.loads(honga.read_text())
    absent = {key for key, record in old["buildings"].items() if record["explicit_no_effect"]}
    records = [
        effect
        for building in data["buildings"].values()
        for variant in building["effect_variants"]
        for effect in variant["effects"]
    ]
    metrics = Counter(effect["metric"] for effect in records)
    resolved = sum(
        bool(building_effects(building, faction))
        for faction in data["factions"].values()
        for building in data["buildings"].values()
        if building["chain"] in faction["chains"]
    )
    return {
        "ruleset": data["ruleset"],
        "source_revision": data["source_revision"],
        "campaign": data["campaign"],
        "historical_static_reference_available": True,
        "latest_game_complete": False,
        "installed_build_validated": False,
        "buildings": len(data["buildings"]),
        "factions": len(data["factions"]),
        "reforms": len(data["reforms"]),
        "commanderies": len(data["commanderies"]),
        "regions": len(data["regions"]),
        "resolved_faction_building_pairs": resolved,
        "building_coverage": thaw(data["coverage"]),
        "honga_details_sha256": hashlib.sha256(honga.read_bytes()).hexdigest(),
        "formerly_unpublished_building_effects_recovered": sorted(absent & set(data["buildings"])),
        "formerly_unpublished_building_effects_absent_from_historical_snapshot": sorted(
            absent - set(data["buildings"])
        ),
        "normalized_variant_effect_counts": dict(sorted(metrics.items())),
        "unmodeled_effect_ids_preserved_for_audit": sorted(
            {effect["effect"] for effect in records if effect["metric"] == "unmodeled"}
        ),
        "modeled_effects_with_unresolved_scope": sorted(
            {
                effect["effect"]
                for effect in records
                if effect["metric"] != "unmodeled" and effect["scope"] == "unmodeled"
            }
        ),
        "limitations": [
            "Historical game 1.2.0 data; later patches and DLC/start dates are not included.",
            "Full land adjacency is missing; joint cross-border effects need an explicit map.",
            "Population, corruption, taxation and fertility use static inputs; "
            "city levels may be optimized or explicitly fixed.",
            "Original ruler career bonuses require that leader profile; successor traits differ.",
            "Dynamic faction resources, diplomacy/trade, court assignments, character equipment, "
            "rank bonuses, construction schedules and scripted conditions are outside this model.",
            "Normalized unmodeled effects remain preserved; their absence from income does not "
            "mean those effects do not exist in the game.",
            "Yellow Turban permanent traits use explicit reviewed bundle mappings corroborated "
            "by a public guide; activation scripts are absent from the snapshot.",
        ],
        "reference_files": [
            {
                "path": str(path.relative_to(Path(__file__).parents[3])),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
            for path in sorted(DATA.glob("*.json"))
        ],
        "source_files": sorted(
            {
                record["url"]: thaw(record)
                for collection in (
                    data["sources"],
                    data["geography"]["sources"],
                    data["rules"]["sources"],
                )
                for record in collection
            }.values(),
            key=lambda row: row["url"],
        ),
    }


def main() -> None:
    result = audit_reference()
    output = Path("reports/three-kingdoms-historical-readiness.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        f"Historical reference: {result['buildings']} buildings, "
        f"{result['factions']} factions, {result['commanderies']} commanderies"
    )


if __name__ == "__main__":
    main()
