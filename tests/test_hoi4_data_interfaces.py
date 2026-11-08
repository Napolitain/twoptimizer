"""Reference inspection stays separate from a runnable, validated gameplay scenario."""

import asyncio
import json

import pytest
from textual.widgets import Button, DataTable, Select, Static, TabbedContent

from games.hoi4.cli import main as data_cli
from games.hoi4.data_pipeline import public_import, resolved_import
from tests.support.ui import QuickRunner
from twoptimizer.__main__ import main
from twoptimizer.errors import ApplicationError
from twoptimizer.hoi4_data import (
    COUNTRIES,
    army_summary,
    country_summary,
    economy_summary,
    inspect_reference,
    literal_building,
    source_selection_summary,
    source_summary,
    state_source,
)
from twoptimizer.hoi4_data_screen import HoI4DataScreen
from twoptimizer.tui import OptimizerApp


def test_reference_report_keeps_source_and_target_separate_and_caller_owned():
    report = inspect_reference("all")
    assert {country["tag"] for country in report["countries"]} == set(COUNTRIES)
    assert report["scenario_ready"] is False
    manifest = report["manifest"]
    assert manifest["requested_target"]["version"] == "1.19.4"
    assert manifest["requested_target"]["reference_validated_against_target"] is False
    assert manifest["source"]["game_patch"] is None
    assert manifest["coverage"]["validated_scenarios"] == 0
    dependencies = report["dependencies"]
    assert "graph" not in dependencies
    assert dependencies["runnable_scenario_established"] is False
    assert dependencies["counts"]["nodes"] > 0
    assert len(dependencies["reference_issues"]) == sum(
        dependencies["counts"]["reference_issues"].values()
    )
    assert dependencies["unevaluated_mechanics"]
    report["countries"][0]["states"].clear()
    assert inspect_reference()["countries"][0]["states"]


def test_reference_cli_text_json_and_export(tmp_path, capsys):
    assert main(["hoi4", "data"]) == 0
    text = capsys.readouterr().out
    assert "France (FRA)" in text and "Literal declarations" in text
    assert "Source patch unverified" in text and "1.19.4 / 0bdb" in text
    assert "balanced_children_of_incomplete_parent" in text
    assert "complete child statements recovered: 5" in text
    assert "Declared dependencies:" in text
    assert "Base template requirements:" in text
    assert "effective requirements remain unresolved" in text
    assert "do not resolve inheritance" in text
    assert "Requested gameplay DLC: all enabled" in text
    assert "FRA: partial source selection at 1936.01.01.12" in text
    assert "Candidate OOB references: FRA_1936_nsb" in text
    assert "Raw selection remains partial; supported derived facts appear in Army/Economy" in text
    assert "74 deployed division records" in text
    assert "35 CIV · 8 MIL · 11 dockyards" in text
    assert "440/456 resolved" in text
    assert "Sourced patch corrections: 10 applied" in text
    assert "DLC branches unselected" not in text
    assert "unselected order-of-battle variants" not in text
    assert "excluded from line unknown" not in text
    path = tmp_path / "reference.json"
    assert main(["hoi4", "data", "--country", "all", "--json", "--output", str(path)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == json.loads(path.read_text())
    assert len(printed["countries"]) == len(COUNTRIES)
    assert len(printed["countries"][0]["source"]["sha256"]) == 64
    assert printed["manifest"]["source_diagnostics"]
    assert printed["countries"][0]["source_selection"]["fully_resolved_country"] is False
    assert printed["countries"][0]["oob_candidates"]
    assert printed["scenario_ready"] is False


def test_reference_template_requirements_retain_candidate_context_and_source_quantities():
    report = inspect_reference("FRA")
    candidate = next(
        row
        for row in report["countries"][0]["oob_candidates"]
        if row["source"]["path"].endswith("FRA_1936.txt")
    )
    template = next(row for row in candidate["templates"] if row["name"] == "Division d'Infanterie")
    summary = template["base_requirements"]
    assert candidate["source"]["sha256"] and not candidate["branch_selected"]
    assert summary["base_equipment"]["infantry_equipment"] == 910
    assert summary["base_manpower"] == 9600 and summary["base_training_days"] == 120
    assert not summary["effective_requirements_resolved"]
    assert summary["units"][0]["definitions"][0]["source"]["sha256"]
    assert "base_requirements" not in summary["template"]


def test_source_selection_summary_retains_unknowns_and_supports_absent_selection():
    profile = inspect_reference()["countries"][0]
    profile["source_selection"]["blockers"] = [{"field": "unknown_condition"}]
    profile["source_selection"]["oob_references"] = []
    assert "1 unknown-condition blockers" in source_selection_summary(profile)
    assert "Candidate OOB references: none recorded" in source_selection_summary(profile)
    assert "0 candidate OOB references" in country_summary(profile)
    del profile["source_selection"]
    assert "source selection unavailable" in source_selection_summary(profile)
    assert "source selection unavailable" in country_summary(profile)


@pytest.mark.parametrize("arguments", [["data", "--country", "unknown"], ["optimize"], []])
def test_reference_cli_rejects_invalid_country_and_gameplay_actions(arguments):
    with pytest.raises(SystemExit) as error:
        data_cli(arguments)
    assert error.value.code == 2


def test_reference_loader_errors_and_output_failure(monkeypatch, capsys, tmp_path):
    with pytest.raises(ApplicationError, match="Unknown HoI4 country"):
        inspect_reference("missing")
    assert main(["hoi4", "data", "--output", str(tmp_path)]) == 2
    assert "Cannot save HoI4 reference report" in capsys.readouterr().err

    def missing():
        raise FileNotFoundError("missing manifest")

    monkeypatch.setattr(public_import, "load_reference_manifest", missing)
    assert main(["hoi4", "data"]) == 2
    assert "Cannot read HoI4 reference data: missing manifest" in capsys.readouterr().err


def test_missing_and_repeated_state_declarations_are_not_resolved_as_gameplay():
    state = {
        "base_building_blocks": [
            {
                "declarations": [
                    {"field": "arms_factory", "value": 1},
                    {"field": "arms_factory", "value": 2},
                ]
            }
        ]
    }
    assert literal_building(state, "industrial_complex") == "—"
    assert literal_building(state, "arms_factory") == "1, 2"
    report = inspect_reference()
    report["manifest"]["source_diagnostics"] = []
    assert "None recorded." in source_summary(report)


def test_reference_inspector_click_keyboard_and_total_war_flow():
    async def exercise():
        app = OptimizerApp(runner_factory=QuickRunner)
        async with app.run_test(size=(120, 48)) as pilot:
            await pilot.pause()
            assert not app.query_one("#hoi4-data").display
            assert not app.query_one("#run", Button).disabled
            app.query_one("#game", Select).value = "hoi4"
            await pilot.pause()
            assert app.query_one("#hoi4-data").display
            assert app.query_one("#run", Button).disabled
            assert await pilot.click("#hoi4-data")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, HoI4DataScreen)
            table = screen.query_one("#hoi4-states", DataTable)
            assert table.row_count == len(inspect_reference()["countries"][0]["states"])
            assert screen.query_one("#hoi4-country", Select).value == "FRA"
            await pilot.click("#hoi4-country")
            await pilot.press("down", "enter")
            await pilot.pause()
            assert screen.query_one("#hoi4-country", Select).value == "ENG"
            assert "United Kingdom (ENG)" in str(
                screen.query_one("#hoi4-country-summary", Static).render()
            )
            table.focus()
            await pilot.press("down")
            await pilot.pause()
            assert table.cursor_row == 1
            assert str(screen.profile["states"][1]["id"]) in str(
                screen.query_one("#hoi4-state-source", Static).render()
            )
            screen.query_one("#hoi4-tabs", TabbedContent).active = "hoi4-source-tab"
            await pilot.pause()
            assert "validated scenarios: 0" in str(
                screen.query_one("#hoi4-coverage", Static).render()
            )
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen is not screen
            assert app.query_one("#run", Button).disabled
            app.query_one("#game", Select).value = "rome2"
            await pilot.pause()
            assert not app.query_one("#hoi4-data").display
            assert not app.query_one("#run", Button).disabled

    asyncio.run(exercise())


def test_reference_inspector_missing_data_and_close_button(monkeypatch):
    def missing():
        raise FileNotFoundError("missing manifest")

    async def exercise():
        app = OptimizerApp(runner_factory=QuickRunner)
        async with app.run_test(size=(120, 48)) as pilot:
            await pilot.pause()
            monkeypatch.setattr(public_import, "load_reference_manifest", missing)
            app.push_screen(HoI4DataScreen())
            await pilot.pause()
            assert app.screen.query_one("#hoi4-states", DataTable).row_count == 0
            assert "missing manifest" in str(
                app.screen.query_one("#hoi4-country-summary", Static).render()
            )
            await pilot.click("#hoi4-close")
            await pilot.pause()
            assert not isinstance(app.screen, HoI4DataScreen)

    asyncio.run(exercise())


def test_state_source_carries_hash_and_explicit_unresolved_coverage():
    state = inspect_reference()["countries"][0]["states"][0]
    text = state_source(state)
    assert state["source"]["sha256"] in text and state["source"]["path"] in text
    assert "unresolved state/history/building statements" in text
    assert "not declared" in text


def test_derived_report_preserves_country_evidence_and_shares_only_equipment_summary():
    report = inspect_reference("all")
    summary = report["resolved_reference"]
    assert summary["available"] and not summary["full_version_validated"]
    assert "equipment" not in summary
    assert summary["equipment_counts"]["statuses"]["resolved_base"] > 0
    assert not summary["scenario_ready"]
    for profile in report["countries"]:
        derived = profile["derived"]
        assert derived["country"] == profile["tag"] and not derived["scenario_ready"]
        assert {"army", "modifiers", "states", "variants"} <= derived.keys()
        assert "equipment" not in derived
    france = report["countries"][0]
    assert france["derived"]["states"]["totals"]["category_shared_slot_capacity"] == 205
    assert "579,000" in army_summary(france)
    assert "42,197,733" in economy_summary(france)
    assert "stability_factor: 0.05" in economy_summary(france)
    france["derived"]["army"]["divisions"].clear()
    assert len(inspect_reference()["countries"][0]["derived"]["army"]["divisions"]) == 74


def test_template_base_requirements_use_guarded_patches_without_rewriting_source(monkeypatch):
    profile = public_import.load_reference_country("FRA")
    template = profile["oob_candidates"][0]["templates"][0]
    template.update(
        regiments=[{**template["regiments"][0], "unit": "anti_air"}],
        support=[],
        unresolved_statements=[],
    )
    monkeypatch.setattr(public_import, "load_reference_country", lambda _tag: profile)
    report = inspect_reference()
    needs = report["countries"][0]["oob_candidates"][0]["templates"][0]["base_requirements"]
    assert needs["base_equipment"] == {"anti_air_equipment": 24}
    source_unit = next(
        row for row in public_import.load_reference_equipment()["units"] if row["id"] == "anti_air"
    )
    assert source_unit["need"][0]["declarations"][0]["value"] == 20
    corrected_unit = needs["units"][0]["definitions"][0]
    correction = corrected_unit["need"][0]["declarations"][0]["patch_overlay"]
    assert correction["target_field_supported"] and correction["release_source"]
    assert report["template_patch_corrections"]["full_version_validated"] is False


def test_missing_derived_manifest_keeps_literal_inspection_usable(monkeypatch):
    def missing():
        raise FileNotFoundError("missing derived manifest")

    monkeypatch.setattr(resolved_import, "load_resolved_manifest", missing)
    report = inspect_reference()
    assert report["countries"][0]["states"]
    assert not report["resolved_reference"]["available"]
    assert "missing derived manifest" in source_summary(report)
    assert "Derived data unavailable" in army_summary(report["countries"][0])
    assert "Derived data unavailable" in economy_summary(report["countries"][0])


def test_corrupt_country_supplement_does_not_hide_other_countries(monkeypatch):
    original = resolved_import.load_resolved_country

    def checked(tag):
        if tag == "FRA":
            raise ValueError("Reference artifact checksum mismatch: armies/FRA.json")
        return original(tag)

    monkeypatch.setattr(resolved_import, "load_resolved_country", checked)
    report = inspect_reference("all")
    assert "checksum mismatch" in report["countries"][0]["derived_error"]
    assert "FRA derived data unavailable" in source_summary(report)
    assert report["countries"][1]["derived"]["country"] == "ENG"


def test_unknown_economic_values_stay_unknown_in_both_presentations():
    profile = inspect_reference()["countries"][0]
    totals = profile["derived"]["states"]["totals"]
    totals["category_shared_slot_capacity"] = None
    totals["declared_resource_deposits"]["coal"] = None
    totals["declared_factories"]["industrial_complex"] = None
    profile["derived"]["states"]["landmark_country_modifiers"]["stability_factor"] = None
    summary = economy_summary(profile)
    assert "unknown category base" in summary
    assert "coal: unknown" in summary
    assert "Factories: unknown CIV" in summary
    assert "Landmark contributions under declared ownership: stability_factor: unknown" in summary
    assert "effective free construction slots" in summary
    assert "readiness unresolved" in army_summary(profile)


def test_army_economy_tabs_fit_small_terminal_and_support_mouse_and_keyboard():
    async def exercise():
        app = OptimizerApp(runner_factory=QuickRunner)
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            app.query_one("#game", Select).value = "hoi4"
            app.push_screen(HoI4DataScreen())
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, HoI4DataScreen)
            close = screen.query_one("#hoi4-close", Button)
            assert close.region.bottom <= screen.size.height
            assert screen.query_one("#hoi4-states", DataTable).size.height >= 4
            assert await pilot.click("#--content-tab-hoi4-army-tab")
            await pilot.pause()
            assert screen.query_one("#hoi4-tabs", TabbedContent).active == "hoi4-army-tab"
            assert "74 deployed division records" in str(
                screen.query_one("#hoi4-army", Static).render()
            )
            await pilot.press("right")
            await pilot.pause()
            assert screen.query_one("#hoi4-tabs", TabbedContent).active == "hoi4-economy-tab"
            assert "205 category base" in str(screen.query_one("#hoi4-economy", Static).render())
            assert await pilot.click("#--content-tab-hoi4-source-tab")
            await pilot.pause()
            assert "Equipment base economics:" in str(
                screen.query_one("#hoi4-coverage", Static).render()
            )
            await pilot.press("escape")
            await pilot.pause()
            assert app.query_one("#run", Button).disabled

    asyncio.run(exercise())
