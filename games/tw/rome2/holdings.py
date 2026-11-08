"""Joint Rome II holdings with shared food and explicitly scoped effects.

The historical single-province model remains unchanged. These holdings compose
its placement, exact income products and solver backends with cross-province
recipient routing and one faction-wide political choice.
"""

import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from games.tw.immutable import freeze
from games.tw.rome2 import building_constraints
from games.tw.rome2.catalog import load_data
from games.tw.rome2.holding_scopes import validate_economic_scope
from games.tw.rome2.model import Economy
from games.tw.rome2.scenario import Scenario


@dataclass(frozen=True, slots=True)
class HoldingScenario(Scenario):
    provinces: tuple[Scenario, ...] = ()
    adjacency: tuple[tuple[str, str], ...] = ()

    @classmethod
    def from_provinces(cls, provinces, adjacency, *, required_buildings=(), forbidden_buildings=()):
        provinces = tuple(provinces)
        if not provinces:
            raise ValueError("Joint holdings require at least one province")
        names = {p.name for p in provinces}
        if len(names) != len(provinces):
            raise ValueError("Joint province names must be distinct")
        if len({p.faction for p in provinces}) != 1:
            raise ValueError("Joint provinces must belong to one faction")
        if len({(p.all_technologies, p.technology_profile) for p in provinces}) != 1:
            raise ValueError("Joint provinces must share one faction research profile")
        sites = tuple(s for p in provinces for s in p.sites)
        if len({s.id for s in sites}) != len(sites):
            raise ValueError("Joint regions must be distinct")
        borders = tuple(tuple(pair) for pair in adjacency)
        if any(len(p) != 2 or p[0] == p[1] or not set(p) <= names for p in borders):
            raise ValueError("Borders must join two different selected provinces")
        if len({frozenset(pair) for pair in borders}) != len(borders):
            raise ValueError("List each border once")
        return cls(
            faction=provinces[0].faction,
            sites=sites,
            name="Together · " + " + ".join(p.name for p in provinces),
            provinces=provinces,
            adjacency=borders,
            all_technologies=provinces[0].all_technologies,
            technology_profile=provinces[0].technology_profile,
            required_buildings=required_buildings,
            forbidden_buildings=forbidden_buildings,
        )

    @classmethod
    def from_dict(cls, record):
        result = cls.from_provinces(
            tuple(Scenario.from_dict(p) for p in record["provinces"]),
            record["adjacency"],
            required_buildings=record.get("required_buildings", ()),
            forbidden_buildings=record.get("forbidden_buildings", ()),
        )
        expected = result.to_dict()
        if set(record) != set(expected) or any(
            record[key] != expected[key] or type(record[key]) is not type(expected[key])
            for key in expected
        ):
            raise ValueError("Joint report metadata differs from its province settings")
        return result

    def to_dict(self):
        return {
            "faction": self.faction,
            "name": self.name,
            "joint": True,
            "all_technologies": self.all_technologies,
            "technology_profile": self.technology_profile,
            "provinces": [province.to_dict() for province in self.provinces],
            "adjacency": [list(pair) for pair in self.adjacency],
            **building_constraints.fields(self),
        }


class HoldingEconomy(Economy):
    def __init__(self, scenario: HoldingScenario, data=None):
        validated = HoldingScenario.from_provinces(
            scenario.provinces,
            scenario.adjacency,
            required_buildings=scenario.required_buildings,
            forbidden_buildings=scenario.forbidden_buildings,
        )
        if validated != scenario:
            raise ValueError("Use HoldingScenario.from_provinces for consistent joint settings")
        self.scenario = scenario
        self.data = load_data() if data is None else freeze(data)
        self.locals = {
            p.name: Economy(p, self.data, required_candidates=scenario.required_buildings)
            for p in scenario.provinces
        }
        if not self.locals:
            raise ValueError("Use HoldingScenario.from_provinces to define joint holdings")
        first = next(iter(self.locals.values()))
        self.faction, self.parties, self.party_effects = (
            first.faction,
            first.parties,
            first.party_effects,
        )
        if any(e.party_effects != self.party_effects for e in self.locals.values()):
            raise ValueError("Joint provinces must share the same political choices")
        self.candidates = {
            site: rows for e in self.locals.values() for site, rows in e.candidates.items()
        }
        building_constraints.validate(scenario, self.data["buildings"], self.candidates)
        for building in {
            key: row for rows in self.candidates.values() for key, row in rows.items()
        }.values():
            for raw in building["effects"]:
                validate_economic_scope(raw)
        self.roles = {pair: role for e in self.locals.values() for pair, role in e.roles.items()}
        self.owners = {site: key for key, e in self.locals.items() for site in e.candidates}
        self.borders = {frozenset(pair) for pair in scenario.adjacency}
        self.exclusions = sum((e.exclusions for e in self.locals.values()), Counter())
        self.decisions, self.party_variables = {}, {}

    def build(self, native=False):
        from games.tw.rome2.holding_compiler import HoldingCompiler

        return HoldingCompiler(self).build(native)

    def evaluate(self, layout, party):
        from games.tw.rome2.holding_evaluation import evaluate

        return evaluate(self, layout, party)

    def warm_values(self, reference):
        from games.tw.rome2.holding_evaluation import warm_values

        return warm_values(self, reference)


def joint_model_fingerprint():
    """Separate identity for joint mathematics; legacy proof identity stays stable."""
    from games.tw.rome2.provenance import model_fingerprint

    digest = hashlib.sha256(model_fingerprint().encode())
    root = Path(__file__).parent
    for name in (
        "holdings.py",
        "holding_compiler.py",
        "holding_evaluation.py",
        "holding_scopes.py",
    ):
        digest.update(name.encode())
        digest.update((root / name).read_bytes())
    return digest.hexdigest()
