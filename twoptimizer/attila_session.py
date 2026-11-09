"""Run-local Attila preparation and independently validated proof reuse."""

from __future__ import annotations

import csv
import json
from copy import deepcopy
from dataclasses import dataclass, field
from time import perf_counter
from typing import TYPE_CHECKING, Any

from games.optimization.cancellation import Cancelled
from games.optimization.competition import BinaryModel, Result, solve
from games.tw.attila.game import AttilaGame
from games.tw.attila.loader import AttilaLoader
from games.tw.attila.model import ModelSnapshot, SnapshotOptions, compile_scenario, load_attila
from games.tw.attila.modifiers import catalog
from games.tw.attila.scenario import Scenario
from games.tw.attila.traits import profile
from twoptimizer.attila_incumbents import checked, model_identity, retain
from twoptimizer.catalog import ROOT
from twoptimizer.holdings import adjacency_mapping, has_campaign_borders
from twoptimizer.session_cache import trim_cache

if TYPE_CHECKING:
    from twoptimizer.models import RunConfig


def native_factions():
    """The settled comparison command's imported, identified faction profiles."""
    return [
        AttilaGame.Factions(f)
        for f in catalog()["faction_slugs"]
        if not any(s in f for s in ("separatist", "rebel"))
        and profile(f)["ruling_party_identified"]
    ]


def faction_metadata():
    """Read source labels and settled/nomadic eligibility without building a model."""
    with (ROOT / "attila/data/factions_table.tsv").open() as stream:
        return {
            row[0]: {"name": row[4], "nomadic": "nomadic" in row[2]}
            for row in csv.reader(stream, delimiter="\t")
            if row[0].startswith("att_fact_")
        }


def signature(model: BinaryModel) -> str:
    """Reuse a proof only when every variable, coefficient and bound matches."""
    return model.fingerprint()


@dataclass(frozen=True, slots=True)
class PreparedAttila:
    snapshot: ModelSnapshot
    province_ids: tuple[str, ...]
    province_names: tuple[str, ...]


def _preparation_key(config: RunConfig) -> str:
    record = config.to_dict()
    record["attila"] = config.attila.to_dict()
    for key in ("algorithm", "seconds", "workers"):
        record.pop(key)
    # Search knobs do not change the compiled economic model.
    record["attila"].pop("seed")
    return json.dumps(record, sort_keys=True)


def campaign_scenario(config: RunConfig) -> Scenario | None:
    """Merge optional requirements and map borders into caller-owned campaign inputs."""
    campaign = _border_scenario(config)
    options = config.constraints
    if not (options.required_buildings or options.forbidden_buildings) and (
        options.minimum_religious_influence is None
    ):
        return campaign
    data = campaign.to_dict() if campaign is not None else {}
    rules = data.setdefault("building_rules", [])
    rules.extend({"buildings": [key], "minimum": 1} for key in options.required_buildings)
    rules.extend({"buildings": [key], "maximum": 0} for key in options.forbidden_buildings)
    if options.minimum_religious_influence is not None:
        data.setdefault("targets", []).extend(
            {
                "metric": "religion:state",
                "scope": "province",
                "target": province,
                "value": options.minimum_religious_influence,
            }
            for province in config.holdings
        )
    return Scenario(data)


def _border_scenario(config: RunConfig) -> Scenario | None:
    campaign = config.attila.campaign
    if config.adjacency is None and (not config.joint or has_campaign_borders(config)):
        return campaign
    data = campaign.to_dict() if campaign is not None else {}
    mapping = adjacency_mapping(config)
    if "adjacency" in data:
        supplied = data["adjacency"]
        normalized = {key: sorted(supplied.get(key, ())) for key in config.holdings}
        if set(supplied) - set(config.holdings) or normalized != {
            key: sorted(neighbors) for key, neighbors in mapping.items()
        }:
            raise ValueError(
                "Campaign adjacency conflicts with the selected neighboring provinces."
            )
    else:
        data["adjacency"] = mapping
    return Scenario(data)


@dataclass(slots=True)
class AttilaSession:
    """Optional batch state; a one-case worker requires no persistent state."""

    reuse_proofs: bool = False
    prior: dict[str, dict[str, Any]] = field(default_factory=dict)
    proofs: dict[str, Result] = field(default_factory=dict)
    incumbents: dict[str, Result] = field(default_factory=dict)
    _parser_key: str | None = None
    _parser: AttilaLoader | None = None
    _prepared_key: str | None = None
    _prepared: PreparedAttila | None = None

    def clear(self) -> None:
        self.prior.clear()
        self.proofs.clear()
        self.incumbents.clear()
        self._parser_key = None
        self._parser = None
        self._prepared_key = None
        self._prepared = None

    def trim(self, limit: int) -> None:
        trim_cache(self.prior, limit)
        trim_cache(self.proofs, limit)
        trim_cache(self.incumbents, limit)

    def parser(self, config: RunConfig) -> AttilaLoader:
        key = json.dumps(
            [config.faction, config.religion, config.attila.to_dict()["region_fertility"]],
            sort_keys=True,
        )
        if self._parser is None or key != self._parser_key:
            parser = load_attila(
                AttilaGame.Factions(config.faction), AttilaGame.Religion[config.religion]
            )
            for assignment in config.attila.region_fertility:
                matches = [
                    r
                    for r in parser.regions.values()
                    if assignment.region in (r.name, r.print_name)
                ]
                if len(matches) != 1:
                    raise ValueError(f"Unknown or ambiguous region: {assignment.region}")
                matches[0].fertility = assignment.value
            self._parser_key, self._parser = key, parser
        return self._parser

    def prepare(self, config: RunConfig) -> PreparedAttila:
        key = _preparation_key(config)
        if self._prepared is not None and key == self._prepared_key:
            return self._prepared
        scenario = campaign_scenario(config)
        parser = self.parser(config)
        provinces = [parser.provinces[key] for key in config.holdings]
        technologies = config.attila.technologies
        if technologies is None and config.research == "none":
            technologies = ()
        snapshot = compile_scenario(
            provinces,
            SnapshotOptions(
                fertility=config.fertility,
                city_level=config.attila.city_level,
                building_level=config.attila.building_level,
                military=config.attila.military,
                technologies=None if technologies is None else frozenset(technologies),
                scenario=scenario,
            ),
        )
        prepared = PreparedAttila(
            snapshot,
            tuple(p.name for p in provinces),
            tuple(p.print_name for p in provinces),
        )
        self._prepared_key, self._prepared = key, prepared
        return prepared

    def solve(
        self, config: RunConfig, prepared: PreparedAttila, **observers
    ) -> tuple[Result, str | None, bool]:
        model = prepared.snapshot.model
        may_reuse = self.reuse_proofs and config.algorithm == "cp-sat"
        identity = model_identity(model)
        key = identity if may_reuse else None
        previous = checked(model, self.incumbents.get(identity))
        result = self._cached_optimum(key)
        if result is None and may_reuse and key in self.prior:
            result = _restore_proof(prepared.snapshot, self.prior[key])
        reused = result is not None
        if result is None:
            result = self._search(config, model, previous, observers)
        result = retain(model, result, previous)
        if result.status in {"FEASIBLE", "OPTIMAL"} and result.values is not None:
            candidate = checked(model, result)
            assert candidate is not None
            self.incumbents.pop(identity, None)
            self.incumbents[identity] = candidate
        if key is not None and result.status == "OPTIMAL":
            self.proofs[key] = deepcopy(result)
        if (
            reused
            and result.values is not None
            and not model.feasible(result.values, integral=not result.relaxation)
        ):
            raise RuntimeError("Comparison result did not validate")
        return result, key, reused

    @staticmethod
    def _search(config, model, previous, observers):
        started = perf_counter()
        hints = {} if previous is None else {"hint_values": previous.values}
        try:
            return solve(
                model,
                config.algorithm,
                seconds=config.seconds,
                seed=config.attila.seed,
                workers=config.workers,
                **hints,
                **observers,
            )
        except Cancelled:
            if previous is None:
                raise
            return Result(
                config.algorithm,
                "UNKNOWN",
                seconds=perf_counter() - started,
                workers=config.workers,
                detail="Cancelled after validating a previous Attila layout",
            )

    def _cached_optimum(self, key: str | None) -> Result | None:
        if key is None:
            return None
        result = self.proofs.get(key)
        if result is not None and result.status != "OPTIMAL":
            # Interrupted searches are valid incumbents, not reusable proofs.
            self.proofs.pop(key)
            return None
        return deepcopy(result)


def _restore_proof(snapshot: ModelSnapshot, previous: dict[str, Any]) -> Result | None:
    """A saved status is insufficient: replay decisions and check the exact bound."""
    economy = snapshot.economy
    assert economy is not None
    if previous.get("status") != "OPTIMAL" or previous.get("selected") is None:
        return None
    selected = set(previous["selected"])
    if not selected <= economy.by_id.keys():
        return None
    auxiliary = {variable.name(): monomial for monomial, variable in economy.products.items()}
    model = snapshot.model
    values = [economy.evaluate({auxiliary.get(name, (name,)): 1}, selected) for name in model.names]
    value = float(model.profit @ values + model.offset)
    if not _matches_saved_proof(model, values, value, previous):
        return None
    return Result(
        "cp-sat",
        "OPTIMAL",
        seconds=previous["solve_seconds"],
        objective=value,
        bound=previous["bound"],
        values=values,
        detail="Reused validated optimal case with identical compiled model",
    )


def _matches_saved_proof(model, values, value, previous) -> bool:
    return (
        model.feasible(values)
        and previous.get("income") is not None
        and previous.get("bound") is not None
        and abs(value - previous["income"]) < 1e-5
        and abs(value - previous["bound"]) < 1e-5
    )
