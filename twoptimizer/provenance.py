"""Hashes of the bundled model, source data and application scenario preparation."""

import hashlib
from pathlib import Path

from twoptimizer.catalog import ROOT


def source_files(game):
    if game == "rome2":
        paths = [
            ROOT / "rome2" / name
            for name in (
                "model.py",
                "compiler.py",
                "linear.py",
                "optimization.py",
                "backends.py",
                "scenario.py",
                "placement.py",
                "catalog.py",
                "records.py",
                "provenance.py",
                "effects.py",
                "world.py",
                "holdings.py",
                "holding_compiler.py",
                "holding_evaluation.py",
                "holding_scopes.py",
                "building_constraints.py",
                "data/economy_catalog.json",
                "data/special_buildings_coverage.json",
                "data/world.json",
                "data/world_modifiers.json",
            )
        ]
    elif game == "shogun2":
        paths = [
            ROOT / "shogun2" / name
            for name in (
                "model.py",
                "scenario.py",
                "catalog.py",
                "records.py",
                "effects.py",
                "constraints.py",
                "data/rules.json",
            )
        ] + [
            ROOT / "multigame/data/shogun2.json",
            ROOT / "competition.py",
            ROOT / "sparse.py",
            ROOT / "resources.py",
        ]
    else:
        paths = [
            *sorted((ROOT / "attila/data").glob("*.tsv")),
            *[
                ROOT / "attila/data" / name
                for name in (
                    "online_buildings.json",
                    "online_factions.json",
                    "online_modifiers.json",
                )
            ],
            *[
                ROOT / name
                for name in (
                    "attila/economy.py",
                    "attila/effect_index.py",
                    "attila/algebra.py",
                    "attila/compiler.py",
                    "attila/compact.py",
                    "attila/reporting.py",
                    "attila/scenario.py",
                    "attila/scenario_validation.py",
                    "attila/records.py",
                    "attila/building_rules.py",
                    "attila/special_slots.py",
                    "catalog.py",
                    "immutable.py",
                    "attila/model.py",
                    "context.py",
                    "comparison.py",
                    "building.py",
                    "entity.py",
                    "region.py",
                    "province.py",
                    "problem.py",
                    "solver_ortools.py",
                    "solver_cpsat.py",
                    "solver_highs.py",
                    "parser/parser.py",
                    "parser/parser_attila.py",
                )
            ],
            ROOT / "competition.py",
            ROOT / "sparse.py",
            ROOT / "resources.py",
        ]
    paths.append(ROOT / "immutable.py")
    paths.append(ROOT / "highs_backend.py")
    paths.append(ROOT / "maps/catalog.py")
    map_path = ROOT / game / "data/campaign_map.json"
    if map_path.exists():
        paths.append(map_path)
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    application = Path(__file__).parent
    application_paths = [
        application / "requests.py",
        application / "models.py",
        application / "constraint_options.py",
        application / "constraint_comparison.py",
        application / "service.py",
        application / "session.py",
        application / "holdings.py",
        application / "progress.py",
        application / "adapters" / "model_stats.py",
        application / "adapters" / f"{game}.py",
    ]
    if game == "rome2":
        application_paths.append(application / "adapters" / "rome_models.py")
    if game in {"attila", "rome2"}:
        application_paths.append(
            application / ("attila_session.py" if game == "attila" else "rome_session.py")
        )
    for path in application_paths:
        hashes[f"twoptimizer/{path.relative_to(application)}"] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    return hashes
