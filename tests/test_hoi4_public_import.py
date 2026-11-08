"""Public reference data keeps literal facts separate from unresolved game rules."""

import hashlib
import json

import pytest

from games.hoi4.data_pipeline import public_import as public
from games.hoi4.data_pipeline.syntax import ScriptSyntaxError
from games.hoi4.planning.time import CampaignDate
from tests.support.hoi4 import write_source as _write_source


@pytest.fixture
def imported(public_source, tmp_path):
    output = tmp_path / "reference"
    manifest = public.build_public_reference(public_source, output)
    return public_source, output, manifest


def test_literal_totals_exclude_conditional_and_future_buildings(imported):
    _, output, manifest = imported
    france = public.load_reference_country("fra", output)
    assert france["literal_state_totals"] == {
        "state_count": 1,
        "industrial_complex": 2,
        "arms_factory": 1,
    }
    assert [row["field"] for row in france["states"][0]["unresolved_history_statements"]] == [
        "if",
        "1939.1.1",
    ]
    assert manifest["unresolved_state_owners"][0]["path"] == "history/states/2.txt"
    assert manifest["coverage"]["validated_scenarios"] == 0
    assert manifest["source"]["game_patch"] is None
    assert not manifest["requested_target"]["reference_validated_against_target"]
    assert manifest["requested_ruleset"]["gameplay_dlc_policy"] == "all_enabled"
    assert not manifest["requested_ruleset"]["source_branches_resolved"]


def test_templates_keep_duplicate_battalions_and_unselected_branches(imported):
    _, output, _ = imported
    candidates = public.load_reference_country("FRA", output)["oob_candidates"]
    assert all(not candidate["branch_selected"] for candidate in candidates)
    regular = candidates[0]
    assert len(regular["templates"][0]["regiments"]) == 2
    assert regular["production_lines"][0]["declarations"][0]["value"] == 4
    partial = candidates[1]
    assert partial["templates"][0]["name"] == "Preserved"
    assert partial["production_lines"][0]["declarations"][0]["value"] == 99
    assert partial["production_lines"][0]["parent_incomplete"]
    assert partial["parse_diagnostics"][0]["unclosed_parent_line"] == 2


def test_equipment_inheritance_and_computed_lua_are_not_evaluated(imported):
    _, output, _ = imported
    equipment = public.load_reference_equipment(output)
    inherited = equipment["equipment"][1]
    assert [row["field"] for row in inherited["declarations"]] == ["archetype", "active"]
    assert equipment["units"][0]["need"][0]["declarations"][0]["value"] == 100
    buildings = json.loads((output / "building_rules.json").read_text())
    defines = buildings["numeric_defines"]["declarations"]
    assert [(row["field"], row["value"]) for row in defines] == [
        ("BASE_FACTORY_SPEED", 4),
        ("POWERED_FACTORY_SPEED", 5),
    ]


def test_sources_and_generated_artifacts_are_checksummed(imported):
    source, output, manifest = imported
    for row in manifest["input_sources"]:
        assert hashlib.sha256((source / row["path"]).read_bytes()).hexdigest() == row["sha256"]
    for row in manifest["artifacts"]:
        assert hashlib.sha256((output / row["path"]).read_bytes()).hexdigest() == row["sha256"]
    assert public.load_reference_manifest(output) == manifest


def test_rebuild_is_deterministic_and_leaves_supplementary_evidence(imported):
    source, output, _ = imported
    before = {path.relative_to(output): path.read_bytes() for path in output.rglob("*.json")}
    evidence = output / "rules_evidence.json"
    evidence.write_text('{"independent": true}')
    public.build_public_reference(source, output)
    assert all((output / name).read_bytes() == content for name, content in before.items())
    assert json.loads(evidence.read_text()) == {"independent": True}


def test_loader_returns_owned_data_and_rejects_path_traversal(imported):
    _, output, _ = imported
    france = public.load_reference_country("FRA", output)
    france["states"].clear()
    assert len(public.load_reference_country("FRA", output)["states"]) == 1
    with pytest.raises(ValueError, match="Unknown reference country"):
        public.load_reference_country("../../manifest", output)


def test_wrong_revision_or_modified_checkout_cannot_claim_pinned_provenance(
    public_source, tmp_path, monkeypatch
):
    with monkeypatch.context() as patch:
        patch.setattr(public, "SOURCE_REVISION", "0" * 40)
        with pytest.raises(ValueError, match="Expected public source revision"):
            public.build_public_reference(public_source, tmp_path / "wrong")
    _write_source(public_source, "history/states/new.txt", "state = { id = 99 }")
    with pytest.raises(ValueError, match="changed or untracked"):
        public.build_public_reference(public_source, tmp_path / "dirty")


def test_malformed_nested_prefix_is_not_repaired(tmp_path):
    path = _write_source(tmp_path, "broken.txt", "outer = {\n inner = { value = 1\n}")
    inputs = public.SourceInputs(tmp_path)
    with pytest.raises(ScriptSyntaxError):
        inputs.document(path)
    bad_quote = _write_source(tmp_path, "quote.txt", 'name = "unterminated')
    with pytest.raises(ScriptSyntaxError):
        inputs.document(bad_quote, allow_prefix=True)


def test_missing_source_and_oversized_output_fail_cleanly(tmp_path):
    with pytest.raises(ValueError, match="history/states"):
        public.build_public_reference(tmp_path / "absent", tmp_path / "output")
    with pytest.raises(ValueError, match="500 KiB"):
        public._write(tmp_path / "large.json", {"huge": "x" * 512000})
    assert not (tmp_path / "large.json").exists()
    with pytest.raises(ValueError, match="both an inspection start"):
        public.build_public_reference(tmp_path, tmp_path, inspection_start=CampaignDate(1936, 1, 1))


def test_bundled_country_coverage_and_hashes():
    manifest = public.load_reference_manifest()
    assert {row["tag"] for row in manifest["countries"]} == set(public.COUNTRIES)
    assert manifest["coverage"]["owned_state_records"] == sum(
        len(public.load_reference_country(tag)["states"]) for tag in public.COUNTRIES
    )
    for artifact in manifest["artifacts"]:
        content = (public.REFERENCE_ROOT / artifact["path"]).read_bytes()
        assert len(content) < 500 * 1024
        assert hashlib.sha256(content).hexdigest() == artifact["sha256"]
    catalog = manifest["selection_catalog"]
    content = (public.REFERENCE_ROOT / catalog["path"]).read_bytes()
    assert hashlib.sha256(content).hexdigest() == catalog["sha256"]


@pytest.mark.parametrize("values", [[2, 3], ["@count"], [True]])
def test_ambiguous_factory_declarations_do_not_become_numeric_totals(values):
    states = [
        {
            "base_building_blocks": [
                {
                    "declarations": [
                        {"field": "industrial_complex", "value": value} for value in values
                    ]
                }
            ]
        }
    ]
    assert public._totals(states) == {"state_count": 1}


def test_requested_ruleset_projection_stays_separate_from_base_facts(public_source, tmp_path):
    catalog = tmp_path / "dlc.json"
    catalog.write_text(json.dumps({"dlcs": [{"script_id": "x", "gameplay": True}]}))
    output = tmp_path / "selected"
    public.build_public_reference(
        public_source,
        output,
        inspection_start=CampaignDate(1936, 1, 1, 12),
        dlc_catalog_path=catalog,
    )
    profile = public.load_reference_country("FRA", output)
    source = profile["source_selection"]
    capitals = [row["value"] for row in source["candidate_scalars"] if row["field"] == "capital"]
    assert capitals == [1, 2]
    assert [
        row["value"] for row in profile["country_declarations"] if row["field"] == "capital"
    ] == [1]
    assert source["oob_references"][0]["value"] == "FRA_1936"
    assert source["idea_operations"][0]["identifiers"] == ["civilian_economy"]
    assert source["technology_blocks"][0]["declarations"][0]["field"] == "infantry_weapons"
    assert not source["fully_resolved_country"]
    manifest = public.load_reference_manifest(output)
    assert (
        manifest["selection_catalog"]["sha256"] == hashlib.sha256(catalog.read_bytes()).hexdigest()
    )
