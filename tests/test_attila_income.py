"""Income defaults, real Roman tax effects, imported traits and omissions."""

import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

from games.tw.attila.economy import Economy
from games.tw.attila.model import SnapshotOptions, compile_scenario, load_attila
from games.tw.attila.modifiers import modifier_profile, semantics, technology_profile
from games.tw.attila.scenario import Scenario
from games.tw.attila.tools.import_factions import parse_faction
from games.tw.competition import BinaryModel, solve
from games.tw.enums import ProblemState
from games.tw.models.game_attila import AttilaGame
from games.tw.problem import Problem
from games.tw.region import Region
from games.tw.solver_ortools import SolverOrTools
from tests.support.attila import building, province

NO_MODIFIERS = {"technology_effects": False, "religion_traits": False}


def game(faction, religion="orthodox", *, context):
    context.instance = SimpleNamespace(
        faction=AttilaGame.Factions[faction], religion=SimpleNamespace(value=religion)
    )


def test_default_income_selects_taxed_roman_wealth_over_larger_gross_wealth(context):
    context.instance = None
    r = Region("r", context=context)
    p = province("p", r)
    problem = Problem(context=context)
    assert problem.objective_mode == "income"
    problem.add_province(p)
    data = Path(__file__).parents[1] / "games/tw/attila/data/building_effects_junction_table.tsv"
    with data.open() as stream:
        tax = next(
            float(amount)
            for b, effect, scope, amount in csv.reader(stream, delimiter="\t")
            if b == "att_bld_roman_east_civic_governor_5_legendary"
            and effect == "att_effect_province_tax_rate"
        )
    assert tax == 8
    candidates = [
        building(
            r,
            "gross",
            ("economy_gdp_industry", "building_to_building_own", 100),
            upkeep=10,
        ),
        building(
            r,
            "roman",
            ("economy_gdp_industry", "building_to_building_own", 95),
            ("province_tax_rate", "province_to_province_own", tax),
            upkeep=5,
        ),
        building(r, "health", ("sanitation_buildings", "region_to_region_own", 1)),
    ]
    for b in candidates:
        assert isinstance(problem.problem, SolverOrTools)
        b.lp_variable = problem.problem.solver.BoolVar(b.name)
    problem.problem.create_constraint(
        "choice",
        [candidates[0].lp_variable, candidates[1].lp_variable],
        constraint_fn=lambda x: x <= 1,
    )
    problem.state = ProblemState.CONSTRAINTS_ADDED
    problem.add_objective()
    model = BinaryModel.from_solver(problem.problem.solver)
    for algorithm in ("cp-sat", "highs"):
        result = solve(model, algorithm)
        assert result.status == "OPTIMAL"
        assert result.objective == pytest.approx(97.6)
        selected = {n for n, v in zip(model.names, result.values, strict=False) if v > 0.5}
        assert "roman" in selected and "gross" not in selected
        assert problem.economy is not None
        report = problem.economy.evaluate_layout(selected)
        assert report["finances"]["total"]["tax_bonus_income"] == pytest.approx(7.6)
        assert report["finances"]["total"]["building_upkeep"] == 5
        assert report["finances"]["total"]["net_income"] == pytest.approx(97.6)


def test_ere_tariffs_corruption_and_upkeep_have_separate_channels(context):
    game("ATT_FACT_EASTERN_ROMAN_EMPIRE", context=context)
    r = Region("r", context=context)
    p = province("p", r)
    building(
        r,
        "factory",
        ("economy_gdp_industry", "building_to_building_own", 200),
        ("province_tax_rate", "province_to_province_own", 20),
        upkeep=10,
    )
    economy = Economy(
        [p],
        scenario={
            **NO_MODIFIERS,
            "base_tariffs": 40,
            "provinces": {"p": {"corruption_percent": 50}},
        },
    )
    report = economy.evaluate_layout({"factory"})
    assert report["finances"]["total"] == pytest.approx(
        {
            "wealth": 200,
            "tax_bonus_income": 40,
            "corruption_loss": 120,
            "tax_income": 120,
            "building_upkeep": 10,
            "trade_income": 60,
            "other_recurring_income": 0,
            "net_income": 170,
        }
    )
    assert report["objective"] == 170
    interest = next(t for t in report["faction_traits"]["traits"] if "interest" in t["text"])
    assert interest["status"] == "excluded_by_requested_objective"


def test_venedian_farm_bonus_and_other_income_penalties(context):
    game("ATT_FACT_VENEDI", context=context)
    r = Region("r", context=context)
    p = province("p", r)
    for name, effect in (
        ("farm", "economy_gdp_agriculture_farming"),
        ("cattle", "economy_gdp_agriculture_animal_husbandry"),
        ("industry", "economy_gdp_industry"),
        ("commerce", "economy_gdp_trade_local"),
        ("sea", "economy_gdp_trade_sea"),
        ("culture", "economy_gdp_culture"),
    ):
        building(r, name, (effect, "building_to_building_own", 100))
    e = Economy([p], scenario=NO_MODIFIERS)
    assert e.evaluate(e.wealth(r), set(e.by_id)) == 600


def test_garamantian_fertility_affects_food_and_wealth_and_desert_sanitation(context):
    game("ATT_FACT_GARAMANTES", context=context)
    r = Region("r", context=context)
    building(
        r,
        "farm",
        ("economy_gdp_fertility_agriculture", "building_to_building_own", 100),
        ("food_production_fertility", "region_to_region_own", 10),
    )
    e = Economy([province("p", r)], scenario=NO_MODIFIERS)
    assert e.evaluate(e.fertility(r), {"farm"}) == 3  # fixture base fertility 2
    assert e.evaluate(e.food(r), {"farm"}) == 30
    assert e.evaluate(e.wealth(r), {"farm"}) == 300
    assert e.evaluate(e.sanitation(r), {"farm"}) == 2


def test_venedian_farms_remove_only_their_own_order_and_squalor_penalties(context):
    game("ATT_FACT_VENEDI", context=context)
    r = Region("r", context=context)
    p = province("p", r)
    building(
        r,
        "att_bld_barbarian_farm_1",
        ("public_order_base", "province_to_province_own", -5),
        ("sanitation_squalor_buildings", "region_to_region_own", 4),
    )
    building(
        r,
        "factory",
        ("public_order_base", "province_to_province_own", -2),
        ("sanitation_squalor_buildings", "region_to_region_own", 3),
    )
    e = Economy([p], scenario=NO_MODIFIERS)
    assert e.evaluate(e.public_order(p), set(e.by_id)) == -2
    assert e.evaluate(e.sanitation(r), set(e.by_id)) == -3


def test_sassanid_capitals_and_tribute_count_once_with_multiple_regions(context):
    game("ATT_FACT_SASSANID_EMPIRE", context=context)
    a, b = Region("a", context=context), Region("b", context=context)
    e = Economy(
        [province("p", a, b)],
        scenario={
            **NO_MODIFIERS,
            "campaign": {"province_capitals_held": 3, "base_tribute": 100},
        },
    )
    assert [e.evaluate(e.sanitation(r), set()) for r in (a, b)] == [3, 3]
    assert e.evaluate(e.objective(), set()) == 200
    assert e.evaluate_layout(set())["finances"]["total"]["other_recurring_income"] == 200


def test_axum_trade_food_is_a_provincial_total_and_trade_bonus_applies_once(context):
    game("ATT_FACT_AXUM", context=context)
    a, b, c = (
        Region("a", context=context),
        Region("b", context=context),
        Region("c", context=context),
    )
    e = Economy(
        [province("p", a, b), province("q", c)],
        scenario={
            **NO_MODIFIERS,
            "base_tariffs": 100,
            "campaign": {"active_trade_routes": 6},
        },
    )
    report = e.evaluate_layout(set())
    assert report["province_food"] == {"p": 150, "q": 150}
    assert report["finances"]["total"]["trade_income"] == 110


def test_peace_subsidy_is_once_per_faction_not_per_province(context):
    game("ATT_FACT_LAKHMIDS", context=context)
    e = Economy(
        [province("p", Region("a", context=context)), province("q", Region("b", context=context))],
        scenario={**NO_MODIFIERS, "campaign": {"at_peace_with_sassanids": True}},
    )
    assert e.evaluate(e.objective(), set()) == 500
    missing = Economy(e.provinces, scenario=NO_MODIFIERS)
    assert missing.evaluate(missing.objective(), set()) == 0
    assert any(
        t.get("required_input") == "at_peace_with_sassanids" for t in missing.traits["traits"]
    )


def test_disabled_roman_technology_is_not_an_active_bonus():
    parser = load_attila(
        AttilaGame.Factions.ATT_FACT_EASTERN_ROMAN_EMPIRE,
        AttilaGame.Religion.CHRIST_ORTHODOX,
    )
    profile = technology_profile(parser.context.instance)
    assert "Improved Plumbing" in profile["disabled_legacy"]
    assert "Improved Plumbing" not in profile["active"]
    assert all(f["source"] != "Improved Plumbing" for f in profile["facts"])
    # Even end-state building access must honor the known legacy disables.
    p = next(p for p in parser.provinces.values() if p.print_name == "Aegyptus")
    economy = compile_scenario([p], SnapshotOptions(fertility=5)).economy
    assert economy is not None
    assert economy.modifiers["technologies"]["active"] == profile["active"]
    for b in economy.buildings:
        assert b.metadata is not None
        for alternatives in b.metadata["requirements_by_culture"].get("eastern-roman", []):
            assert not set(alternatives) <= set(profile["disabled_legacy"])


@pytest.mark.parametrize(
    "faith,kind,category,value",
    [
        ("celtic", "wealth_percent", "industry", 3),
        ("judaism", "wealth_percent", "industry", 5),
        ("grecoroman", "sanitation", None, 2),
        ("eastern", "corruption_percent", None, -5),
    ],
)
def test_state_religion_economic_bonus_has_exact_imported_semantics(
    context, faith, kind, category, value
):
    game("ATT_FACT_EASTERN_ROMAN_EMPIRE", faith, context=context)
    report, effects = modifier_profile(context.instance, scenario={"technology_effects": False})
    assert len(effects) >= 1
    assert any(
        rule.kind == kind and (category is None or category in rule.categories) and amount == value
        for _, rule, _, amount in effects
    )
    assert report["religion"]["source_sha256"]


def test_rule_parser_does_not_flatten_subsistence_trade_or_unrest_percentages():
    assert semantics("Wealth: +25% from subsistence")[0][0].categories == ("subsistence",)
    assert semantics("Trade income: +10% trade agreement tariffs")[0][0].kind == "tariff_percent"
    assert (
        semantics("Public order: -5% penalty due to presence of other religions")[0][0].kind
        == "religious_order_percent"
    )
    assert not semantics("Unknown bonus: +10000")


@pytest.mark.parametrize(
    "faith,building_id",
    [
        ("PAGAN_SLAVIC", "att_slav_religion_major_1"),
        ("PAGAN_SEMITIC", "att_bld_eos_religion_semitic_major_1"),
    ],
)
def test_new_faiths_keep_their_source_building_aliases(faith, building_id):
    from games.tw.parser.parser_attila import ParserAttila

    parser = object.__new__(ParserAttila)
    parser.religion = AttilaGame.Religion[faith]
    assert parser.building_is_of_religion(building_id)


def test_opposition_party_is_not_given_to_the_ruler():
    html = (
        "<p>Campaign</p>main_attila<!-- Faction Group Effects --><div "
        'style="margin-left:64px">Sunscorched: +2 sanitation<br></div><!-- '
        'Political Parties Effects --><div style="margin-left:64px">Playable:'
        " False<br>Initial Power: 30<br>Trade tariffs: +999%<br></div><div "
        'style="margin-left:64px">Playable: True<br>Initial Power: '
        '70<br>Trade tariffs: +50%<br></div><div class="table-responsive">'
    )
    result = parse_faction(html)
    assert result["faction_traits"] == ["Trade tariffs: +50%"]
    assert result["other_party_traits"] == [["Trade tariffs: +999%"]]
    with pytest.raises(ValueError):
        parse_faction("new source layout")


@pytest.mark.parametrize(
    "data",
    [
        {"faction_traits": "yes"},
        {"campaign": {"active_trade_routes": -1}},
        {"campaign": {"province_capitals_held": True}},
        {"campaign": {"at_peace_with_sassanids": 1}},
        {"projects": [{"region": "r", "base_cost": 100, "category": "fake"}]},
    ],
)
def test_invalid_economic_campaign_conditions_fail(data):
    with pytest.raises((ValueError, TypeError)):
        Scenario(data)
