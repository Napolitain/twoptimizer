"""Offline end-to-end import tests retain source identities and fail on drift."""

import json
from urllib.parse import parse_qs, urlparse

import pytest

from games.tw.attila.tools import import_modifiers
from games.tw.rome2 import import_public


def flight_page(payload, build="123"):
    flight = "1:" + json.dumps(payload)
    script = "self.__next_f.push(" + json.dumps([1, flight]) + ");"
    return f"Steam build {build}<script>{script}</script>"


def technology_payload():
    return {
        "icons": [],
        "fx": [["+5% tax rate"]],
        "nodes": [["Tax", None, None, None, [0], None, None, [], None, None, None]],
    }


def religion_payload():
    return [
        {
            "id": f"att_rel_{i}",
            "effect": [
                "$",
                "span",
                None,
                {"className": "text-sm text-green", "children": "+1 public order"},
            ],
        }
        for i in range(14)
    ]


def test_modifier_import_replays_all_cached_faction_trees(tmp_path):
    for slug in import_modifiers.SLUGS:
        (tmp_path / f"{slug}.html").write_text(flight_page(technology_payload()))
    (tmp_path / "religions.html").write_text(flight_page(religion_payload()))
    output = tmp_path / "modifiers.json"
    report = import_modifiers.import_data(tmp_path, output, offline=True)
    assert len(report["faction_slugs"]) >= 29
    assert len(report["religions"]["records"]) == 14
    tree = report["technologies"]["eastern-roman-empire"]
    assert tree["records"]["Tax"]["effects"] == ["+5% tax rate"]
    assert len(tree["sha256"]) == 64
    assert json.loads(output.read_text()) == report
    (tmp_path / "religions.html").write_text(flight_page(religion_payload(), build="124"))
    with pytest.raises(ValueError, match="mix source game builds"):
        import_modifiers.import_data(tmp_path, output, offline=True)


def test_modifier_parsers_reject_missing_and_duplicate_payloads(tmp_path):
    with pytest.raises(FileNotFoundError):
        import_modifiers.import_data(tmp_path, tmp_path / "missing.json", offline=True)
    assert list(import_modifiers.documents("<script>ignored()</script>")) == []
    with pytest.raises(ValueError, match="No technology"):
        import_modifiers.technologies(flight_page({}))
    payload = technology_payload()
    payload["nodes"] *= 2
    with pytest.raises(ValueError, match="duplicated"):
        import_modifiers.technologies(flight_page(payload))
    with pytest.raises(ValueError, match="14 Grand Campaign"):
        import_modifiers.religions(flight_page([]))
    bad = religion_payload()
    bad[0]["effect"][3]["children"] = 4
    with pytest.raises(ValueError, match="Religion effect"):
        import_modifiers.religions(flight_page(bad))


def detail_page(key, fact="+5% tax rate"):
    return (
        f'<h1>{key}</h1><div id="detail"><h3>Effects</h3>{fact}<br></div>'
        '<table class="table_stat">'
        f"<tr><td>Level Name</td><td>{key}</td></tr>"
        "<tr><td>Building Level</td><td>1</td></tr>"
        "<tr><td>Create Cost</td><td>100</td></tr></table>"
    )


class PublicPages:
    def __init__(self, cache, offline):
        self.records = {}

    def get(self, url):
        query = parse_qs(urlparse(url).query)
        self.records[url] = {"url": url, "sha256": "a" * 64}
        if "b" in query:
            return detail_page(query["b"][0])
        if "t" in query:
            return detail_page(query["t"][0])
        faction = query["f"][0]
        return f'<a href="technology.php?f={faction}&t=tax">Tax</a>'

    def many(self, urls):
        return {url: self.get(url) for url in urls}


def public_fixture(tmp_path, monkeypatch):
    data_dir = tmp_path / "tw/rome2/data"
    data_dir.mkdir(parents=True)
    public_dir = tmp_path / "tw/multigame/data"
    public_dir.mkdir(parents=True)
    catalog = data_dir / "catalog.json"
    factions = {f: {"id": f, "roster_id": "one"} for f in import_public.DLC}
    buildings = {
        "dk_all_city_1": {
            "name": "City",
            "chain": "dk_all_city",
            "construction_cost": 100,
            "facts": ["+5% tax rate"],
            "source_url": "https://example.com/city",
        },
        "east_spice_1": {
            "name": "Spice",
            "chain": "all_mine",
            "construction_cost": 100,
            "facts": [],
            "source_url": "https://example.com/spice",
        },
        "rom_slum_1": {"name": "Slum", "chain": "slum", "facts": []},
    }
    public = {
        "factions": factions,
        "buildings": buildings,
        "rosters": {"one": {"buildings": list(buildings)}},
    }
    (public_dir / "rome2.json").write_text(json.dumps(public))
    catalog.write_text(
        json.dumps(
            {
                "buildings": {},
                "factions": {},
                "regions": {},
                "technologies": {f: {"old": {}} for f in factions},
            }
        )
    )
    tables = {
        "building_effects_junction_table.tsv": [
            [key, "rom_building_tax_level", "5", "this_faction"]
            for key in ["dk_all_city_1", "east_spice_1", "dk_kush_religious_1"]
        ],
        "building_culture_variants_table.tsv": [
            ["east_spice_1", "rom_Eastern", "", "", "Spice"],
            ["dk_kush_religious_1", "rom_Eastern", "", "rom_kush", "Temple"],
        ],
    }
    monkeypatch.setattr(import_public, "DATA", data_dir)
    monkeypatch.setattr(import_public, "CATALOG", catalog)
    monkeypatch.setattr(import_public, "Sources", PublicPages)
    monkeypatch.setattr(import_public, "read_table", tables.__getitem__)
    return catalog


def test_public_import_updates_rosters_spice_variants_and_research(tmp_path, monkeypatch):
    catalog = public_fixture(tmp_path, monkeypatch)
    report = import_public.main(["--offline", "--cache", str(tmp_path / "cache")])
    assert set(report["factions"]) == set(import_public.DLC)
    assert set(report["buildings"]) == {"dk_all_city_1", "east_spice_1", "dk_kush_religious_1"}
    assert len(report["dlc_exclusions"]) == 4
    assert report["raw_variant_supplement"]["buildings"] == ["dk_kush_religious_1"]
    assert report["technologies"]["rom_kush"]["tax"]["facts"] == ["+5% tax rate"]
    assert all(row["complete_public_tree"] for row in report["technology_coverage"].values())
    assert json.loads(catalog.read_text()) == report


@pytest.mark.parametrize(
    ("chain", "expected"),
    [
        ("dk_minor_iron", ("Minor Settlement", "iron")),
        ("dk_saba_marib_dam", ("Sanitation", "Marib Dam")),
        ("dk_military_training", ("Military", "Training")),
        ("east_city_centre", ("City Centre", "City Centre")),
        ("east_town_centre", ("City Centre", "Town Centre")),
    ],
)
def test_dlc_placement_rules(chain, expected):
    assert import_public.dlc_role(chain) == expected


def test_unknown_dlc_chain_and_empty_technology_tree_are_rejected():
    with pytest.raises(ValueError, match="Unclassified"):
        import_public.dlc_role("new_unknown_chain")
    with pytest.raises(ValueError, match="tree missing"):
        import_public.tree_links("<p>No tree</p>", "rom_kush")
    assert import_public.strip_scope("+3 food (all regions)") == "+3 food in all regions"
    assert import_public.strip_scope("+2 food (all provinces)") == "+2 food in all provinces"
