"""Behavioral isolation, model equivalence and typed boundary regressions."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError

import pytest

from games.optimization.competition import solve
from games.tw.attila.builder import BinaryBuilder
from games.tw.attila.comparison import ComparisonOptions, compare_model
from games.tw.attila.context import AttilaContext
from games.tw.attila.enums import AttilaFactions, AttilaReligion, NameType
from games.tw.attila.faction_comparison import signature
from games.tw.attila.game import AttilaGame
from games.tw.attila.model import SnapshotOptions, compile_scenario, load_attila
from tests.support.paths import FIXTURES_ROOT
from twoptimizer.models import BuildingSelection, CaseResult, RunConfig
from twoptimizer.service import solve_case

BASELINES = json.loads((FIXTURES_ROOT / "attila-models.json").read_text())


def load_case(case):
    parser = load_attila(AttilaFactions[case["faction"]], AttilaReligion[case["religion"]])
    provinces = [
        p for name in case["provinces"] for p in parser.provinces.values() if p.print_name == name
    ]
    options = SnapshotOptions(
        fertility=case["fertility"],
        technologies=None if case["technologies"] is None else frozenset(case["technologies"]),
    )
    return parser, provinces, options


@pytest.mark.parametrize("case", BASELINES)
def test_compiled_models_match_recorded_coefficients_and_bounds(case):
    _, provinces, options = load_case(case)
    compiled = compile_scenario(provinces, options)
    assert signature(compiled.model) == case["signature"]
    assert len(compiled.model.names) == case["variables"]
    assert len(compiled.model.lower) == case["constraints"]
    assert compiled.economy is not None
    assert all(not r.buildings for p in provinces for r in p.regions)


def test_interleaved_games_do_not_leak_fertility_catalog_religion_or_solver():
    first_parser, provinces, options = load_case(BASELINES[1])
    first = compile_scenario(provinces, options)
    first_economy = first.economy
    assert first_economy is not None
    selected = set(first_economy.by_id)
    evaluated = first_economy.evaluate_layout(selected)
    second_parser, other_provinces, other_options = load_case(BASELINES[4])
    other = compile_scenario(other_provinces, other_options)
    cold = compile_scenario(provinces, SnapshotOptions(fertility=0, technologies=frozenset()))
    repeated = compile_scenario(provinces, options)
    assert signature(first.model) == signature(repeated.model)
    assert signature(cold.model) != signature(first.model)
    assert first_economy.evaluate_layout(selected) == evaluated
    assert first_parser.context.instance is not second_parser.context.instance
    assert other.economy is not None
    assert first_economy.context.model_builder() is not other.economy.context.model_builder()
    assert all(b.region.context is first_economy.context for b in first_economy.buildings)


def test_concurrent_compilations_share_catalog_but_not_mutable_decisions():
    _, provinces, warm = load_case(BASELINES[1])
    cold = SnapshotOptions(fertility=0, technologies=frozenset())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda options: compile_scenario(provinces, options), [cold, warm]))
    assert [signature(r.model) for r in results] == [c["signature"] for c in BASELINES[:2]]
    assert results[0].economy is not None and results[1].economy is not None
    assert results[0].economy.context.buildings is results[1].economy.context.buildings
    assert results[0].economy.regions[0] is not results[1].economy.regions[0]
    assert all(not r.buildings for p in provinces for r in p.regions)


def test_failed_compilation_leaves_input_and_existing_model_usable():
    _, provinces, _options = load_case(BASELINES[1])
    existing = compile_scenario(provinces, SnapshotOptions(fertility=5))
    contexts = [r.context for p in provinces for r in p.regions]
    with pytest.raises(ValueError, match="Unknown technologies"):
        compile_scenario(
            provinces, SnapshotOptions(fertility=5, technologies=frozenset({"missing"}))
        )
    assert [r.context for p in provinces for r in p.regions] == contexts
    assert all(not r.buildings for p in provinces for r in p.regions)
    result = solve(existing.model, "cp-sat", workers=1)
    assert result.status == "OPTIMAL"
    assert result.objective > 0


def test_typed_comparison_preserves_validated_income_layout_and_proof():
    _, provinces, options = load_case(BASELINES[2])
    compiled = compile_scenario(provinces, options)
    report = compare_model(compiled.model, ComparisonOptions(workers=1), compiled.economy)
    result = report["results"][0]
    assert result["status"] == "OPTIMAL"
    assert report["best_feasible"] == report["upper_bound"] == result["objective"]
    assert result["layout"]["objective"] == result["objective"]
    decoded = json.loads(json.dumps(report))
    assert decoded["results"][0]["selected"] == result["selected"]
    assert decoded["results"][0]["objective"] == result["objective"]


def test_typed_case_serializes_the_existing_worker_and_export_schema():
    config = RunConfig(
        game="shogun2",
        faction="oda",
        province="jap_sado",
        algorithm="cp-sat",
        workers=1,
    )
    result = solve_case(config)
    assert isinstance(result, CaseResult)
    assert all(isinstance(b, BuildingSelection) for b in result.buildings)
    payload = result.to_dict()
    assert payload["request"]["game"] == "shogun2"
    assert result.income is not None
    assert payload["income"] == result.income > 0
    assert payload["solver"]["status"] == "OPTIMAL"
    assert payload["gap_percent"] == 0
    assert payload["buildings"] == [
        {"region": b.region, "building": b.building, "id": b.id} for b in result.buildings
    ]
    decoded = json.loads(json.dumps(payload))
    assert decoded["buildings"] == payload["buildings"]
    assert decoded["solver"] == payload["solver"]
    assert decoded["income"] == result.income
    with pytest.raises(FrozenInstanceError):
        field_name = "faction"
        setattr(config, field_name, "changed")


def test_context_identifiers_and_solver_dependencies_are_local():
    first, second = AttilaContext(), AttilaContext()
    assert first.next_id("R") == second.next_id("R") == "R1"
    assert first.next_id("R") == "R2"
    with pytest.raises(ValueError, match=r"^No game selected$"):
        first.current()
    with pytest.raises(ValueError, match="Create a model builder"):
        first.model_builder()
    source_builder = first.builder = BinaryBuilder()
    first.name_type = NameType.HASH_NAME
    derived = first.for_model(fertility=0)
    assert derived.builder is None and first.builder is source_builder
    inherited = first.for_model()
    assert inherited.fertility == first.fertility
    assert derived.fertility == 0 and first.fertility == 5
    assert derived.name_type is NameType.HASH_NAME
    assert derived.next_id("R") == "R1"


def test_empty_and_mixed_game_inputs_are_rejected_without_mutation():
    with pytest.raises(ValueError, match="at least one province"):
        compile_scenario([], SnapshotOptions(fertility=5))
    _, first, options = load_case(BASELINES[1])
    _, second, _ = load_case(BASELINES[4])
    with pytest.raises(ValueError, match="same loaded game"):
        compile_scenario(first + second, options)
    assert all(not r.buildings for p in first + second for r in p.regions)


def test_game_factories_own_their_contexts_without_a_global_selection():
    eastern = AttilaGame(faction=AttilaFactions.ATT_FACT_EASTERN_ROMAN_EMPIRE)
    western = AttilaGame(faction=AttilaFactions.ATT_FACT_WESTERN_ROMAN_EMPIRE)
    assert eastern.parser.context is not western.parser.context
    assert eastern.parser.context.current() is eastern
    assert western.parser.context.current() is western
    assert eastern.parser.context.buildings is eastern.parser.buildings
    assert western.parser.context.buildings is western.parser.buildings
    assert eastern.parser.faction is AttilaFactions.ATT_FACT_EASTERN_ROMAN_EMPIRE
    assert western.parser.faction is AttilaFactions.ATT_FACT_WESTERN_ROMAN_EMPIRE
