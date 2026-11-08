"""Public evidence parsing preserves uncertainty and never enables special buildings."""

import hashlib
import json

import pytest

from games.tw.multigame.sources import Sources
from games.tw.rome2.audit_sources import observation
from games.tw.rome2.audit_special_buildings import (
    AUDIT,
    honga_detail,
    official_detail,
    refresh_audit,
    source_requests,
)

SOURCE = "https://r2encv2.totalwar.com/en/building/legendaryrom_Roman/index.html"
BUILDING = {
    "id": "legendary",
    "name": "Library",
    "level": 5,
    "occurrences": [{"source_url": SOURCE, "factions": ["rom_rome"]}],
    "effects": [],
}
OFFICIAL = """
<h1>Library</h1>
<ul class="abilities"><li>300 wealth from learning (culture)</li></ul>
<a class="selected" href="/en/building/legendaryrom_Roman"><img data-title="Library"></a>
<a href="/en/building/other"><img data-object='{"effects":["900 wealth from subsistence"]}'></a>
<table class="table requires-table"><tr><td>Buildings
<div class="faction-nested">
<a href="/en/faction/rom_rome"></a>
<a href="/en/building/predecessor"><img data-title="Archives"></a></div>
<div class="faction-nested">
<a href="/en/faction/emp_antony"></a>
<a href="/en/building/other_campaign"><img data-title="Different building"></a></div>
</td></tr><tr><td>Resources
<a href="/en/resource/res_rom_glass"><img data-title="Glassware"></a>
</td></tr></table>
"""
HONGA = """
<h1>Library</h1><div id="article_body">
<table class="table_stat">
<tr><td><p>Level Name</p>legendary</td></tr>
<tr><td><p>Require Resource</p>Marble</td></tr>
<tr><td><p>Require Technology</p>
<a href="technology.php?t=architecture">Architecture</a></td></tr>
</table><h3>Effects</h3>
300 wealth from learning (culture) (this_building)<br>
+36% research rate (this_faction)<br></div>
"""


def test_official_requirements_filter_campaign_without_inventing_caps():
    detail = official_detail(OFFICIAL, BUILDING, SOURCE)
    assert detail["facts"] == ["300 wealth from learning (culture)"]
    predecessor, resource = detail["requirements"]
    assert predecessor["factions"] == ["rom_rome"]
    assert predecessor["links"][0]["name"] == "Archives"
    assert resource["links"][0]["name"] == "Glassware"
    assert "other_campaign" not in json.dumps(detail)
    assert "unique" not in detail


@pytest.mark.parametrize(
    "html",
    [
        "<h1>Access denied</h1>",
        OFFICIAL.replace("/en/building/legendaryrom_Roman", "/en/building/different"),
    ],
)
def test_official_identity_rejects_bad_or_same_name_wrong_building(html):
    with pytest.raises(ValueError, match="identity"):
        official_detail(html, BUILDING, SOURCE)


def test_honga_preserves_requirement_links_and_effect_scopes():
    detail = honga_detail(HONGA, BUILDING, "https://www.honga.net/totalwar/rome2/building.php")
    assert detail["requirements"][0]["value"] == "Marble"
    technology = detail["requirements"][1]
    assert technology["value"] == "Architecture"
    assert technology["links"][0]["url"].endswith("/rome2/technology.php?t=architecture")
    assert detail["facts"][1] == "+36% research rate (this_faction)"
    with pytest.raises(ValueError, match="key"):
        honga_detail(HONGA.replace(">legendary<", ">different<"), BUILDING, SOURCE)


def test_unavailable_sources_are_reported_without_reusing_stale_evidence(tmp_path):
    baseline = {
        "rule_evidence_needed": {"uniqueness": {"status": "unresolved"}},
        "level_five_buildings": [{"id": "legendary", "public_details": [{"old": True}]}],
    }
    audit = refresh_audit(
        baseline, {"buildings": {"legendary": BUILDING}}, Sources(tmp_path, offline=True)
    )
    row = audit["level_five_buildings"][0]
    assert row["status"] == "excluded_pending_rules"
    assert row["unresolved_rules"] == ["uniqueness"]
    assert all("Missing offline source" in detail["error"] for detail in row["public_details"])
    assert audit["public_detail_summary"]["pages_failed"] == 2
    assert audit["public_detail_summary"]["pages_parsed"] == 0
    assert baseline["level_five_buildings"][0]["public_details"] == [{"old": True}]


def test_offline_refresh_preserves_response_hashes_and_all_unresolved_rules(tmp_path):
    requests = source_requests(BUILDING)
    for source_url, html in zip(requests, [OFFICIAL, HONGA], strict=True):
        (tmp_path / (hashlib.sha256(source_url.encode()).hexdigest() + ".html")).write_text(html)
    baseline = {
        "rule_evidence_needed": {"first_builder": {"status": "unresolved"}},
        "level_five_buildings": [{"id": "legendary"}],
    }
    audit = refresh_audit(
        baseline, {"buildings": {"legendary": BUILDING}}, Sources(tmp_path, offline=True)
    )
    details = audit["level_five_buildings"][0]["public_details"]
    assert details[0]["source"]["sha256"] == hashlib.sha256(OFFICIAL.encode()).hexdigest()
    assert details[1]["metadata"]["Level Name"] == "legendary"
    assert audit["public_detail_summary"]["pages_parsed"] == 2
    assert audit["public_detail_summary"]["newly_enabled_buildings"] == 0
    assert audit["level_five_buildings"][0]["unresolved_rules"] == ["first_builder"]


@pytest.mark.parametrize("scope", ["", " (this_building)"])
def test_learning_wealth_is_recognized_by_source_comparison(scope):
    assert observation("300 wealth from learning (culture)" + scope) == (
        "wealth",
        ("culture_learning",),
        300,
    )


def test_bundled_audit_covers_every_special_building_and_records_source_identity():
    audit = json.loads(AUDIT.read_text())
    summary = audit["public_detail_summary"]
    assert summary["buildings"] == 35
    assert summary["pages_checked"] == summary["pages_parsed"] == 65
    assert summary["buildings_with_public_requirements"] == 34
    assert summary["pages_with_numeric_disagreement"] == 0
    assert summary["newly_enabled_buildings"] == 0
    for building in audit["level_five_buildings"]:
        assert set(building["unresolved_rules"]) == set(audit["rule_evidence_needed"])
        assert building["status"] == "excluded_pending_rules"
        for detail in building["public_details"]:
            assert len(detail["source"]["sha256"]) == 64
            assert detail["facts"]
            assert detail["display_vs_catalog_raw"]["raw_not_displayed"] == []
    rekem = next(b for b in audit["level_five_buildings"] if b["id"] == "dk_all_city_5")
    assert all(d["requirements"] == [] for d in rekem["public_details"])
    assert rekem["unresolved_rules"]
