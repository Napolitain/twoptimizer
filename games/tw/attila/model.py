"""Isolated Attila game loading and model compilation, independent of any UI."""

from __future__ import annotations

from copy import copy
from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING

from games.optimization.competition import BinaryModel
from games.tw.attila.construction import Construction
from games.tw.attila.context import AttilaContext
from games.tw.attila.enums import AttilaFactions, AttilaReligion
from games.tw.attila.game import AttilaGame
from games.tw.attila.loader import AttilaLoader
from games.tw.attila.province import Province

if TYPE_CHECKING:
    from games.tw.attila.economy import Economy
    from games.tw.attila.scenario import Scenario


def load_attila(faction: AttilaFactions, religion: AttilaReligion) -> AttilaLoader:
    context = AttilaContext()
    game = AttilaGame(faction=faction, religion=religion, context=context)
    parser = game.parser
    assert isinstance(parser, AttilaLoader)
    parser.parse_building_effects_junction_tables()
    parser.parse_start_pos_tsv(parser.game_dir)
    return parser


@dataclass(frozen=True, slots=True, kw_only=True)
class SnapshotOptions:
    fertility: float
    city_level: int = 4
    building_level: int = 1
    military: bool = False
    objective: str = "income"
    technologies: frozenset[str] | None = None
    scenario: Scenario | dict | None = None


@dataclass(frozen=True, slots=True)
class ModelSnapshot:
    model: BinaryModel
    build_seconds: float
    economy: Economy | None


def _copy_province(province: Province) -> Province:
    """Copy mutable decisions while retaining immutable catalog/effect records."""
    cloned = copy(province)
    cloned.regions = []
    for region in province.regions:
        local = copy(region)
        local.buildings = []
        local.building_chain_to_hashname = region.building_chain_to_hashname.copy()
        cloned.regions.append(local)
    return cloned


def compile_scenario(provinces: list[Province], options: SnapshotOptions) -> ModelSnapshot:
    """Compile an isolated model; caller-owned provinces are never mutated."""
    if not provinces:
        raise ValueError("Select at least one province")
    source = provinces[0].context
    if any(province.context.instance is not source.instance for province in provinces):
        raise ValueError("Joint provinces must belong to the same loaded game")
    start = perf_counter()
    context = source.for_model(fertility=options.fertility)
    problem = Construction(
        objective=options.objective,
        technologies=options.technologies,
        scenario=options.scenario,
        context=context,
    )
    for province in provinces:
        problem.add_province(_copy_province(province))
    regions = [r for p in problem.provinces for r in p.regions]
    for region in regions:
        region.add_buildings()
        region.filter_city_level(options.city_level)
        region.filter_building_level(options.building_level)
        if not options.military:
            region.filter_military()
        region.filter_technologies()
        problem.builder.assign_buildings({b.name: b for b in region.buildings})
    for region in regions:
        region.add_constraints()
    problem.add_objective()
    return ModelSnapshot(
        problem.builder.binary_model(),
        perf_counter() - start,
        problem.economy,
    )
