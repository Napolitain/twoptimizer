"""Run-local Attila preparation and independently validated proof reuse."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from games.tw.attila.model import ModelSnapshot, SnapshotOptions, compile_scenario, load_attila
from games.tw.attila.modifiers import catalog
from games.tw.attila.scenario import Scenario
from games.tw.attila.traits import profile
from games.tw.competition import BinaryModel, Result, solve
from games.tw.models.game_attila import AttilaGame
from games.tw.parser.parser_attila import ParserAttila
from games.tw.sparse import SparseConstraints
from twoptimizer.catalog import ROOT
from twoptimizer.holdings import adjacency_mapping, has_campaign_borders

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
    digest = hashlib.sha256(json.dumps(model.names).encode())
    for array in (model.profit, model.matrix, model.lower, model.upper):
        digest.update(str(array.shape).encode())
        if isinstance(array, SparseConstraints):
            array.update_hash(digest)
        else:
            digest.update(array.tobytes())
    digest.update(str(model.offset).encode())
    return digest.hexdigest()


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
    for key in ("seed", "beam_width", "restarts"):
        record["attila"].pop(key)
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
    _parser_key: str | None = None
    _parser: ParserAttila | None = None
    _prepared_key: str | None = None
    _prepared: PreparedAttila | None = None

    def parser(self, config: RunConfig) -> ParserAttila:
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

    def solve(self, config: RunConfig, prepared: PreparedAttila) -> tuple[Result, str | None, bool]:
        model = prepared.snapshot.model
        may_reuse = self.reuse_proofs and config.algorithm == "cp-sat"
        key = signature(model) if may_reuse else None
        result = self.proofs.get(key) if key is not None else None
        if result is None and may_reuse and key in self.prior:
            result = _restore_proof(prepared.snapshot, self.prior[key])
        reused = result is not None
        if result is None:
            result = solve(
                model,
                config.algorithm,
                seconds=config.seconds,
                seed=config.attila.seed,
                width=config.attila.beam_width,
                restarts=config.attila.restarts,
                workers=config.workers,
            )
        if key is not None:
            self.proofs[key] = result
        if (
            reused
            and result.values is not None
            and not model.feasible(result.values, integral=not result.relaxation)
        ):
            raise RuntimeError("Comparison result did not validate")
        return result, key, reused


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
