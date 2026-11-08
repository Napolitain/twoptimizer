"""Integrated source resolution remains reproducible and exposes partial results honestly."""

import hashlib
import json
import shutil

import pytest

from games.hoi4.data_pipeline import public_import, resolved_import
from tests.support.hoi4 import source_git, write_source


@pytest.fixture
def resolved_source(public_source, tmp_path, monkeypatch):
    write_source(
        public_source,
        "common/ideas/fixture.txt",
        "ideas = { country = { civilian_economy = { do_effect = { is_tutorial = no } "
        "modifier = { industrial_capacity_factory = .123 } } } }",
    )
    source_git(public_source, "add", ".")
    source_git(
        public_source,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-qm",
        "Add a non-tutorial economic effect",
    )
    monkeypatch.setattr(
        public_import, "SOURCE_REVISION", source_git(public_source, "rev-parse", "HEAD")
    )
    reference = tmp_path / "literal"
    public_import.build_public_reference(public_source, reference)
    for name in ("dlc_catalog.json", "patch_overlays.json"):
        shutil.copyfile(public_import.REFERENCE_ROOT / name, reference / name)
    output = tmp_path / "derived"
    manifest = resolved_import.build_resolved_reference(
        public_source, output, reference_root=reference
    )
    return public_source, reference, output, manifest


def test_integrated_import_rebuild_is_deterministic_and_retains_unknowns(resolved_source):
    source, reference, output, manifest = resolved_source
    before = {path.relative_to(output): path.read_bytes() for path in output.rglob("*.json")}
    repeated = resolved_import.build_resolved_reference(source, output, reference_root=reference)
    assert repeated == manifest
    assert before == {
        path.relative_to(output): path.read_bytes() for path in output.rglob("*.json")
    }
    assert manifest["scenario_ready"] is False and manifest["full_version_validated"] is False
    assert len(manifest["countries"]) == 8
    assert manifest["tutorial"] is False
    report = resolved_import.load_resolved_country("FRA", output)
    assert not report["army"]["fully_resolved_starting_army"]
    assert report["modifiers"]["blockers"]  # Fixture deliberately has no technology definitions.
    assert report["modifiers"]["additive_modifiers"]["industrial_capacity_factory"] == 0.123
    equipment = resolved_import.load_resolved_equipment(output)
    child = next(row for row in equipment["equipment"] if row["id"] == "infantry_equipment_0")
    assert child["base_cost_ic"] == 0.43 and child["base_resources"] == {"steel": 2}
    assert child["field_sources"]
    support = resolved_import.load_resolved_support_profile(output)
    assert not support["source_values_complete"] and support["blockers"]
    for artifact in manifest["artifacts"]:
        raw = (output / artifact["path"]).read_bytes()
        assert len(raw) == artifact["bytes"]
        assert hashlib.sha256(raw).hexdigest() == artifact["sha256"]


def test_literal_checksums_and_revision_are_required(resolved_source):
    source, reference, output, _ = resolved_source
    with pytest.raises(ValueError, match="must not overwrite"):
        resolved_import.build_resolved_reference(source, reference, reference_root=reference)
    country = reference / "countries" / "FRA.json"
    country.write_text(country.read_text() + " ")
    with pytest.raises(ValueError, match="checksum mismatch"):
        resolved_import.build_resolved_reference(source, output, reference_root=reference)
    manifest_path = reference / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["source"]["revision"] = "different"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="revision differ"):
        resolved_import.build_resolved_reference(source, output, reference_root=reference)


def test_derived_loaders_own_data_and_detect_changed_artifacts(resolved_source):
    _, _, root, _ = resolved_source
    first = resolved_import.load_resolved_country("FRA", root)
    first["army"]["selected_oobs"].clear()
    assert resolved_import.load_resolved_country("FRA", root)["army"]["selected_oobs"]
    with pytest.raises(ValueError, match="Unknown HoI4 country"):
        resolved_import.load_resolved_country("../../manifest", root)
    artifact = root / "armies" / "FRA.json"
    artifact.write_text(artifact.read_text() + " ")
    with pytest.raises(ValueError, match="checksum mismatch"):
        resolved_import.load_resolved_country("FRA", root)


def test_chunked_equipment_keeps_all_records_with_bounded_files(tmp_path, monkeypatch):
    monkeypatch.setattr(resolved_import, "MAX_ARTIFACT_BYTES", 50)
    records = [{"id": str(index), "evidence": "some evidence"} for index in range(10)]
    parts = resolved_import._equipment_parts(tmp_path, records)
    assert len(parts) > 1
    assert [
        row for part in parts for row in resolved_import._checked_artifact(tmp_path, part)
    ] == records
    assert resolved_import._equipment_parts(tmp_path, []) == []
    with pytest.raises(ValueError, match="500 KiB"):
        resolved_import._write(tmp_path, "too-big.json", {"data": "x" * 512000})
    with pytest.raises(ValueError, match="inside its catalog"):
        resolved_import._checked_artifact(tmp_path, {"path": "../outside.json"})
    with pytest.raises(ValueError, match="Conflicting input"):
        resolved_import._source_union(
            [{"path": "same", "sha256": "a"}], [{"path": "same", "sha256": "b"}]
        )


def test_bundled_derived_catalog_closes_real_equipment_and_army_gaps():
    manifest = resolved_import.load_resolved_manifest()
    assert len(manifest["countries"]) == 8
    assert manifest["patch_counts"] == {"applied": 10}
    support = resolved_import.load_resolved_support_profile()
    assert support["source_values_complete"] and support["contributions"]
    expected = {
        "FRA": 74,
        "ENG": 38,
        "USA": 36,
        "GER": 30,
        "ITA": 46,
        "JAP": 60,
        "SOV": 138,
        "CHI": 85,
    }
    for tag, count in expected.items():
        country = resolved_import.load_resolved_country(tag)
        assert country["army"]["summary"]["division_count"] == count
        assert country["army"]["summary"]["divisions_with_unresolved_requirements"] == 0
        assert country["army"]["stockpile_totals"] is None
        assert not country["scenario_ready"]
        assert country["modifiers"]["selected_country_modifiers_complete"]
        assert country["states"]["totals"]["state_count"] > 0
        assert not country["states"]["effective_economy_resolved"]
    equipment = {row["id"]: row for row in resolved_import.load_resolved_equipment()["equipment"]}
    assert equipment["infantry_equipment_1"]["base_cost_ic"] == 0.5
    assert equipment["support_equipment_1"]["base_resources"] == {"aluminium": 1, "steel": 2}
    assert equipment["small_plane_cas_airframe_1"]["requires_variant"]
    assert equipment["gw_armored_car_equipment"]["base_cost_ic"] == 3
    france = resolved_import.load_resolved_country("FRA")
    assert france["modifiers"]["additive_modifiers"][
        "industrial_capacity_factory"
    ] == pytest.approx(-0.1)
    assert france["states"]["totals"]["declared_factories"] == {
        "industrial_complex": 35,
        "arms_factory": 8,
        "dockyard": 11,
    }
    assert france["states"]["landmark_country_modifiers"] == {"stability_factor": 0.05}
    assert len(france["variants"]) == france["army"]["summary"]["variant_count"]
    designer = next(row for row in france["variants"] if row["modules"])
    assert designer["base"]["field_sources"]
    assert designer["country_and_mio_modifiers_applied"] is False
    for artifact in manifest["artifacts"]:
        content = (resolved_import.DERIVED_ROOT / artifact["path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == artifact["sha256"]


def test_rebuild_cli_uses_explicit_paths(resolved_source, capsys):
    source, reference, output, _ = resolved_source
    resolved_import.main(
        [
            "--source-root",
            str(source),
            "--reference",
            str(reference),
            "--output",
            str(output),
            "--start",
            "1936.1.1.12",
        ]
    )
    assert len(json.loads(capsys.readouterr().out)["countries"]) == 8
