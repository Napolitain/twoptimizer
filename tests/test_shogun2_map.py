"""Display geometry must cover the source provinces without inventing adjacency."""

import json
from copy import deepcopy
from hashlib import sha256

import pytest

from games.tw.shogun2 import import_map


def source_fixture():
    html = (
        '<img src="map.png" width="10" height="10" usemap="#m_outline">'
        '<map id="m_outline">'
        '<area href="regions/jap_kozuka.html" shape="poly" coords="0,0,3,0,0,3">'
        '<area href="regions/jap_owari.html" shape="poly" coords="4,0,7,0,4,3">'
        '<area href="specialities.html" shape="circle" coords="9,9,1">'
        "</map>"
    )
    source = {
        "url": import_map.PROVINCES,
        "sha256": sha256(html.encode()).hexdigest(),
        "bytes": len(html.encode()),
    }
    names = {"jap_kozuke": {"name": "Kozuke"}, "jap_owari": {"name": "Owari"}}
    return html, source, names


def adjacency_fixture(names):
    digest = "54d3d67eb5aa6e1f9c3003d325cfd66f39ecc7ce646336609a3bcaf38931b125"
    return {
        "schema_version": 1,
        "game": "shogun2",
        "campaign": "jap_shogun",
        "regions": {
            key: {"ai_id": index, "x": index * 10, "y": index * 20}
            for index, key in enumerate(names, 1)
        },
        "boundaries": [{"a": "jap_kozuke", "b": "jap_owari", "kind": 1, "distance": 12.5}],
        "sources": [
            {
                "url": f"https://example.com/{i}.pack",
                "pack_sha256": str(i) * 64,
                "pack_bytes": 99,
                "extracted_boundaries_sha256": digest,
            }
            for i in (1, 2)
        ],
        "verification": {
            "normalized_boundaries_sha256": digest,
            "region_count": 2,
            "boundary_count": 1,
            "boundary_kind_counts": {"0": 0, "1": 1},
            "canonical_region_coverage_complete": True,
            "source_ai_ids_equal": True,
            "source_boundary_distances_equal": True,
            "source_coordinates_equal": True,
            "source_graphs_equal": True,
        },
        "limitations": ["Synthetic source fixture"],
    }


def test_display_polygons_do_not_become_verified_borders():
    html, source, names = source_fixture()
    snapshot = import_map.extract_snapshot(html, source)
    report = import_map.map_catalog(snapshot, names)
    kozuke = report["regions"]["jap_kozuke"]
    assert (kozuke["x"], kozuke["y"]) == (1, 1)
    assert kozuke["source_region_id"] == "jap_kozuka"
    assert kozuke["polygon"] == [[0, 0], [3, 0], [0, 3]]
    assert len(report["regions"]) == 2
    assert report["geometry"]["source_image_url"] == "https://shogun2-encyclopedia.com/map.png"
    assert not report["coverage"]["complete"]
    assert report["coverage"]["geometry_complete"]
    assert report["coverage"]["adjacency_kind"] == "unavailable"
    assert report["region_borders"] == report["province_borders"] == []
    assert report["sources"] == [source]


def test_source_boundary_kinds_and_engine_coordinates_are_preserved_separately():
    html, source, names = source_fixture()
    report = import_map.map_catalog(import_map.extract_snapshot(html, source), names)
    adjacency = adjacency_fixture(names)
    import_map.add_adjacency(report, adjacency)
    assert report["region_borders"] == report["province_borders"] == [["jap_kozuke", "jap_owari"]]
    assert report["source_boundary_types"] == {"0": [], "1": [["jap_kozuke", "jap_owari"]]}
    assert report["coverage"]["complete"]
    assert report["coverage"]["adjacency_kind"] == "engine_region_boundaries"
    kozuke = report["regions"]["jap_kozuke"]
    assert (kozuke["x"], kozuke["y"]) == (1, 1)
    assert kozuke["engine_ai_position"] == {"ai_id": 1, "x": 10, "y": 20}
    assert report["sources"][1]["sha256"] == "1" * 64
    assert report["movement_edges"] == []


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("a", "jap_missing", "Invalid or duplicate"),
        ("b", "jap_kozuke", "Invalid or duplicate"),
        ("kind", 2, "Unrecognized engine boundary kind"),
        ("kind", True, "Unrecognized engine boundary kind"),
        ("distance", float("nan"), "Invalid engine boundary distance"),
        ("distance", -1, "Invalid engine boundary distance"),
    ],
)
def test_invalid_engine_boundaries_fail_closed(field, value, message):
    html, source, names = source_fixture()
    report = import_map.map_catalog(import_map.extract_snapshot(html, source), names)
    adjacency = adjacency_fixture(names)
    adjacency["boundaries"][0][field] = value
    with pytest.raises(ValueError, match=message):
        import_map.add_adjacency(report, adjacency)


def test_adjacency_requires_consistent_coverage_and_cross_checks():
    html, source, names = source_fixture()
    report = import_map.map_catalog(import_map.extract_snapshot(html, source), names)
    adjacency = adjacency_fixture(names)
    adjacency["verification"]["source_graphs_equal"] = False
    with pytest.raises(ValueError, match="agreeing"):
        import_map.add_adjacency(report, adjacency)
    adjacency = adjacency_fixture(names)
    adjacency["verification"]["boundary_count"] = 2
    with pytest.raises(ValueError, match="verification counts"):
        import_map.add_adjacency(report, adjacency)
    adjacency = adjacency_fixture(names)
    adjacency["regions"].pop("jap_kozuke")
    with pytest.raises(ValueError, match="region coverage"):
        import_map.add_adjacency(report, adjacency)
    adjacency = adjacency_fixture(names)
    adjacency["regions"]["jap_owari"]["ai_id"] = 1
    with pytest.raises(ValueError, match="region AI identity"):
        import_map.add_adjacency(report, adjacency)
    adjacency = adjacency_fixture(names)
    adjacency["boundaries"].append(adjacency["boundaries"][0])
    with pytest.raises(ValueError, match="Invalid or duplicate"):
        import_map.add_adjacency(report, adjacency)


@pytest.mark.parametrize("rewrite_summary_digest", [False, True])
def test_boundary_corruption_is_rejected_despite_matching_counts(rewrite_summary_digest):
    html, source, names = source_fixture()
    report = import_map.map_catalog(import_map.extract_snapshot(html, source), names)
    adjacency = adjacency_fixture(names)
    adjacency["boundaries"][0]["distance"] += 1
    if rewrite_summary_digest:
        encoded = json.dumps(
            adjacency["boundaries"], sort_keys=True, separators=(",", ":")
        ).encode()
        adjacency["verification"]["normalized_boundaries_sha256"] = sha256(encoded).hexdigest()
    with pytest.raises(ValueError, match="digest differs from audited source extracts"):
        import_map.add_adjacency(report, adjacency)


def test_every_recorded_source_digest_must_match_the_captured_boundaries():
    html, source, names = source_fixture()
    report = import_map.map_catalog(import_map.extract_snapshot(html, source), names)
    adjacency = adjacency_fixture(names)
    adjacency["sources"][1]["extracted_boundaries_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="digest differs from audited source extracts"):
        import_map.add_adjacency(report, adjacency)


def test_boundary_digest_uses_undirected_canonical_order():
    html, source, names = source_fixture()
    report = import_map.map_catalog(import_map.extract_snapshot(html, source), names)
    adjacency = adjacency_fixture(names)
    boundary = adjacency["boundaries"][0]
    boundary["a"], boundary["b"] = boundary["b"], boundary["a"]
    import_map.add_adjacency(report, adjacency)
    assert report["region_borders"] == [["jap_kozuke", "jap_owari"]]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("shape", "circle", "polygon province"),
        ("coords", "0,0,3,0,0", "coordinate pairs"),
        ("coords", "0,0,3,0", "coordinate pairs"),
        ("coords", "0,0,30,0,0,3", "outside"),
        ("coords", "0,0,1,1,2,2", "zero area"),
        ("href", "regions/jap_missing.html", "Unmatched province"),
        ("href", "not_a_province", "Unrecognized province link"),
    ],
)
def test_invalid_source_geometry_is_rejected(field, value, message):
    html, source, names = source_fixture()
    snapshot = import_map.extract_snapshot(html, source)
    snapshot["areas"][0][field] = value
    with pytest.raises(ValueError, match=message):
        import_map.map_catalog(snapshot, names)


def test_duplicate_missing_and_unknown_source_maps_are_rejected():
    html, source, names = source_fixture()
    snapshot = import_map.extract_snapshot(html, source)
    with pytest.raises(ValueError, match="one province image map"):
        import_map.extract_snapshot("<p>No map</p>", source)
    duplicate = deepcopy(snapshot)
    duplicate["areas"].append(duplicate["areas"][0])
    with pytest.raises(ValueError, match="Duplicate province"):
        import_map.map_catalog(duplicate, names)
    missing = deepcopy(snapshot)
    missing["areas"].pop()
    with pytest.raises(ValueError, match="Province coverage"):
        import_map.map_catalog(missing, names)
    invalid = deepcopy(snapshot)
    invalid["schema_version"] = 2
    with pytest.raises(ValueError, match="Unrecognized province map source"):
        import_map.map_catalog(invalid, names)
    invalid = deepcopy(snapshot)
    invalid["image"]["width"] = "0"
    with pytest.raises(ValueError, match="dimensions must be positive"):
        import_map.map_catalog(invalid, names)


def test_cached_online_import_replays_offline_exactly(tmp_path, monkeypatch):
    html, _, names = source_fixture()
    catalog_dir = tmp_path / "multigame/data"
    catalog_dir.mkdir(parents=True)
    (catalog_dir / "shogun2.json").write_text(json.dumps({"regions": names}))
    monkeypatch.setattr(import_map, "ROOT", tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    cache.joinpath(sha256(import_map.PROVINCES.encode()).hexdigest() + ".html").write_text(html)
    snapshot = tmp_path / "source.json"
    adjacency = tmp_path / "adjacency.json"
    adjacency.write_text(import_map.snapshot_text(adjacency_fixture(names)))
    output = tmp_path / "map.json"
    args = [
        "--cache",
        str(cache),
        "--snapshot",
        str(snapshot),
        "--adjacency-source",
        str(adjacency),
        "--output",
        str(output),
    ]
    report = import_map.main(args)
    first = output.read_bytes()
    assert import_map.main([*args, "--offline"]) == report
    assert output.read_bytes() == first
    assert report["source_snapshot"]["sha256"] == sha256(snapshot.read_bytes()).hexdigest()


def test_bundled_geometry_reproduces_all_65_canonical_provinces(tmp_path):
    output = tmp_path / "map.json"
    report = import_map.main(["--offline", "--output", str(output)])
    assert report["coverage"]["region_count"] == report["coverage"]["province_count"] == 65
    assert output.read_bytes() == import_map.OUTPUT.read_bytes()
    assert (
        report["source_snapshot"]["sha256"] == sha256(import_map.SNAPSHOT.read_bytes()).hexdigest()
    )
    assert sum(len(region["polygon"]) for region in report["regions"].values()) == 3107
    assert report["coverage"]["complete"]
    assert report["coverage"]["region_border_count"] == 103
    assert report["coverage"]["boundary_kind_counts"] == {"0": 101, "1": 2}
    assert report["source_boundary_types"]["1"] == [
        ["jap_awa", "jap_awaji"],
        ["jap_buzen", "jap_nagato"],
    ]
    assert all("jap_sado" not in pair for pair in report["region_borders"])
    assert (
        report["adjacency_source_snapshot"]["sha256"]
        == sha256(import_map.ADJACENCY.read_bytes()).hexdigest()
    )
