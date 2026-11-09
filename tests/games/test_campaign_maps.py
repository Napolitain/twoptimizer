"""Complete source graphs, conservative defaults, overrides and exported evidence."""

import csv
import json
from dataclasses import replace

import pytest

from games.tw.attila.scenario import Scenario
from games.tw.immutable import thaw
from games.tw.maps.catalog import (
    load_campaign_map,
    province_borders,
    region_provinces,
    validate_map,
)
from tests.support.ui import result
from twoptimizer.adapters.rome2 import prepare_scenario
from twoptimizer.attila_session import campaign_scenario
from twoptimizer.export import export_session
from twoptimizer.holdings import adjacency_mapping, map_context, resolved_borders
from twoptimizer.models import AttilaOptions, RunConfig
from twoptimizer.requests import default_config, make_jobs


@pytest.mark.parametrize(
    "game, regions, provinces, borders",
    [("attila", 186, 62, 108), ("rome2", 173, 57, 100), ("shogun2", 65, 65, 103)],
)
def test_complete_maps_match_all_campaign_ids_and_preserve_source_metadata(
    game, regions, provinces, borders
):
    data = load_campaign_map(game)
    assert data is not None
    assert data["coverage"]["complete"]
    assert len(data["regions"]) == len(region_provinces(game)) == regions
    assert len({row["province"] for row in data["regions"].values()}) == provinces
    assert len(data["province_borders"]) == borders
    assert data["sources"] and data["limitations"]
    for source in data["sources"]:
        assert source["url"].startswith("https://") and len(source["sha256"]) == 64
    with pytest.raises(TypeError):
        data["coverage"]["complete"] = False


@pytest.mark.parametrize(
    "game, places, expected",
    [
        (
            "attila",
            ("att_prov_thracia", "att_prov_macedonia", "att_prov_africa"),
            (("att_prov_macedonia", "att_prov_thracia"),),
        ),
        (
            "rome2",
            ("rome_main_italia", "rome_main_magna_graecia", "rome_main_africa"),
            (("rome_main_italia", "rome_main_magna_graecia"),),
        ),
        ("shogun2", ("jap_owari", "jap_mikawa", "jap_sado"), (("jap_mikawa", "jap_owari"),)),
    ],
)
def test_selected_map_keeps_only_direct_neighbors_and_never_links_across_seas(
    game, places, expected
):
    assert province_borders(game, places) == expected
    assert province_borders(game, ()) == ()
    assert province_borders(game, (places[0],)) == ()
    assert province_borders(game, ("unknown",)) is None


@pytest.mark.parametrize("game", ["attila", "rome2"])
def test_automatic_defaults_and_explicit_overrides_are_resolved_identically_for_engines(game):
    keys = (
        ("att_prov_thracia", "att_prov_macedonia")
        if game == "attila"
        else ("rome_main_italia", "rome_main_magna_graecia")
    )
    config = replace(default_config(game), provinces=keys, joint=True)
    jobs, _ = make_jobs(config)
    automatic = jobs[0]
    assert automatic.adjacency is None
    borders = resolved_borders(automatic)
    assert borders == (tuple(sorted(keys)),)
    explicit = replace(automatic, adjacency=borders)
    empty = replace(automatic, adjacency=())
    assert resolved_borders(empty) == ()
    assert map_context(automatic)["mode"] == "map"
    assert map_context(explicit)["mode"] == "custom"
    assert map_context(empty)["mode"] == "none"
    if game == "attila":
        auto_scenario, custom_scenario = campaign_scenario(automatic), campaign_scenario(explicit)
        assert auto_scenario is not None and custom_scenario is not None
        assert auto_scenario.to_dict() == custom_scenario.to_dict()
        assert thaw(auto_scenario.adjacency) == adjacency_mapping(automatic)
    else:
        assert prepare_scenario(automatic).to_dict() == prepare_scenario(explicit).to_dict()
        assert prepare_scenario(empty).to_dict()["adjacency"] == []


def test_campaign_adjacency_overrides_map_and_explicit_conflicts_remain_errors():
    keys = ("att_prov_thracia", "att_prov_macedonia")
    config = replace(
        default_config("attila"),
        provinces=keys,
        joint=True,
        attila=AttilaOptions(campaign=Scenario({"adjacency": {}})),
    )
    assert resolved_borders(config) == ()
    assert map_context(config)["mode"] == "campaign"
    scenario = campaign_scenario(config)
    assert scenario is not None and scenario.adjacency == {}
    with pytest.raises(ValueError, match="conflicts"):
        campaign_scenario(replace(config, adjacency=(keys,)))


def test_missing_map_never_silently_means_no_borders(monkeypatch):
    monkeypatch.setattr("twoptimizer.holdings.province_borders", lambda *args: None)
    config = RunConfig(provinces=("rome_main_italia", "rome_main_africa"), joint=True)
    with pytest.raises(ValueError, match="Set neighboring"):
        make_jobs(config)
    assert len(make_jobs(replace(config, adjacency=()))[0]) == 1


def test_effective_map_borders_survive_json_and_csv_exports(tmp_path):
    config = RunConfig(provinces=("rome_main_italia", "rome_main_magna_graecia"), joint=True)
    completed = result(config)
    completed["raw"]["map_context"] = map_context(config)
    path, csv_path = export_session(tmp_path / "map-run.json", [completed])
    saved = json.loads(path.read_text())["cases"][0]
    assert saved["request"]["adjacency"] is None
    assert saved["raw"]["map_context"]["borders"] == [[*config.holdings]]
    with csv_path.open(newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["adjacency_mode"] == "map"
    assert row["adjacency_directed"] == "False"
    assert json.loads(row["adjacency"]) == [[*config.holdings]]


def test_directed_campaign_targets_survive_resolution_and_export(tmp_path):
    source, target = "att_prov_thracia", "att_prov_macedonia"
    outgoing = {source: [target], target: []}
    config = replace(
        default_config("attila"),
        provinces=(source, target),
        joint=True,
        attila=AttilaOptions(campaign=Scenario({"adjacency": outgoing})),
    )
    assert adjacency_mapping(config) == outgoing
    assert resolved_borders(config) == ((source, target),)
    completed = result(config)
    completed["raw"]["map_context"] = map_context(config)
    assert completed["raw"]["map_context"]["directed"] is True
    _, csv_path = export_session(tmp_path / "directed.json", [completed])
    with csv_path.open(newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["adjacency_mode"] == "campaign" and row["adjacency_directed"] == "True"
    assert json.loads(row["adjacency"]) == [[source, target]]


@pytest.mark.parametrize(
    "fault", ["self", "duplicate", "unknown", "projection", "count", "missing"]
)
def test_corrupt_source_graphs_and_coverage_claims_are_rejected(fault):
    data = load_campaign_map("rome2")
    assert data is not None
    broken = thaw(data)
    first = broken["region_borders"][0]
    if fault == "self":
        broken["region_borders"].append([first[0], first[0]])
    elif fault == "duplicate":
        broken["region_borders"].append(first[::-1])
    elif fault == "unknown":
        broken["region_borders"].append([first[0], "missing"])
    elif fault == "projection":
        broken["province_borders"].pop()
    elif fault == "count":
        broken["coverage"]["region_count"] -= 1
    else:
        broken["regions"].pop(first[0])
    with pytest.raises(ValueError):
        validate_map(broken, "rome2", region_provinces("rome2"))
