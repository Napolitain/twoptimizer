# Attila special-building audit

Audit date: 2026-11-08. This pass recovered public evidence of a **missing
faction-capital construction restriction**, identified the exact database fields
needed to implement it, and inventoried 34 special-building candidates. It did
not recover the vanilla values of those fields. No solver candidate or economic
coefficient changed in this audit.

**Current Attila income results are not certified legal campaign layouts.** The
model does not distinguish the faction capital when allowing legendary civic
buildings. Such layouts can overstate attainable income, including indirectly
through repeated faction-wide public-order bonuses. The available evidence
does not justify treating every `legendary` identifier as a one-per-faction cap.
Optional user building limits can express a chosen scenario but do not verify
the missing vanilla rules.

## What the public sources establish

Two independent mod authors describe removing the faction-capital restriction
on legendary or selected tier-five buildings. Bladeuk explicitly identifies
the WRE's repeated faction-wide public-order benefit. IonizedMercury's update
also covers Slavic wonders. These are direct statements about the modifications
their authors made, not a complete vanilla database export. Neither description
enumerates all affected building IDs or establishes a world uniqueness rule.
[Bladeuk, updated 2020-04-02](https://steamcommunity.com/sharedfiles/filedetails/?id=437563994)
and [IonizedMercury, updated 2016-02-25](https://steamcommunity.com/sharedfiles/filedetails/?id=581104077).

The pinned [RPFM Attila schema](https://github.com/Frodo45127/rpfm-schemas/blob/ddd192747ebc12ad1411ce87ed4c2e90b21dff2a/schema_att.ron)
separately defines `building_levels.only_in_capital`, `faction_unique` and
`first_in_world_bundle`, as well as religion and resource requirements. A schema
defines possible columns; it does not supply their vanilla row values. Capital
placement, owning one building, and receiving a first-construction reward are
different mechanics. Captured buildings and a changed capital also require
campaign-state decisions before a static solver can enforce a construction rule.

The [official Empires of Sand description](https://store.steampowered.com/app/343463/Total_War_ATTILA__Empires_of_Sand_Culture_Pack/?l=english)
confirms Himyar's unique capital dam and recurring repairs, costs and flood risk.
The [Honga dam entry](https://www.honga.net/totalwar/attila/building.php?b=att_bld_eos_marib_dam&f=att_fact_himyar&l=en&v=attila)
adds exact identity, construction cost and effects: 500 subsistence wealth,
30% faction-wide agriculture/livestock wealth, and five fertility levels. It
does not expose upkeep. Its fertility description says province while its raw
scope says `building_to_region_own`; both are retained for validation. These
facts are insufficient to enable a permanent, cost-free dam in the income model.

The [official Slavic Nations description](https://store.steampowered.com/app/428730/Total_War_ATTILA_Slavic_Nations_Culture_Pack/?l=english)
confirms wonders with provincial and faction-wide effects and maintenance costs.
Their five exact Honga IDs match existing local records; they were not missing
from the TSVs. The missing information is income metadata and verified
availability. Honga supplies these construction and provincial tax observations:

| Exact ID | Name | Construction | Turns | Province tax bonus |
|---|---|---:|---:|---:|
| `att_slav_wonder_1` | Totem of the Wolf | 50,000 | 8 | +10% |
| `att_slav_wonder_civic_2` | Lunar Shrine of Svarog | 100,000 | 16 | +20% |
| `att_slav_wonder_civic_3` | Temple of the Shimmering Wolves | 150,000 | 32 | +30% |
| `att_slav_wonder_military_2` | Fiery Shrine of Svarog | 100,000 | 16 | +10% |
| `att_slav_wonder_military_3` | Temple of the Blazing Wolves | 150,000 | 32 | +10% |

The source URLs and response hashes for every row are in
[special_building_sources.json](../../games/tw/attila/data/special_building_sources.json).
Honga's civic wonder descriptions also expose conversion modifiers affecting
all regions; these are construction/conversion effects, not recurring wealth.
Missing upkeep is recorded as `null`, never zero.

## Current catalogue coverage

The offline [per-ID report](../../games/tw/attila/data/special_building_audit.json)
preserves names, culture/faction variants, known site rules, income metadata,
every local effect and its raw scope. All unimported availability flags remain
`null`. The selection includes the 27 local `legendary` IDs, the dam, the Royal
Mint, and the five sourced Slavic wonders. This is an explicit audit candidate
set, not proof that every special building has been found.

| Group | IDs | Income metadata | Regional rules / remaining gap |
|---|---:|---|---|
| Latin, Greek and Arian patriarchal chains | 15 | Present | Five known sites and selected religion modeled; raw availability flags absent |
| Roman, Sassanid and barbarian legendary civic buildings | 11 | Present | Faction-capital and uniqueness flags absent |
| Beheading Copse | 1 | Missing; excluded | Upkeep and availability absent |
| Ma'rib Dam | 1 | Missing; excluded | Zafar site identified; upkeep, availability and event state absent |
| Aksum Royal Mint | 1 | Missing; excluded | Exact Aksum variant known; upkeep and capital/uniqueness flags absent |
| Slavic wonders | 5 | Missing; excluded | IDs and effects present; upkeep and availability absent |

There are **26 metadata-covered candidates and eight excluded candidates**.
Twelve candidates have a faction-scoped effect of some kind (including agent or
military effects); one has an adjacent-province effect. These counts do not mean
all those effects are recurring income. For example:

- `att_bld_roman_east_civic_governor_5_legendary` has +1 public order at
  `faction_to_province_own`, in addition to its local/provincial benefits. Its
  effect is modeled; its faction-capital availability is not imported.
- `att_bld_barbarian_civic_market_general_5_legendary_celts` has +15% commerce
  wealth at `province_to_regions_own_in_adjacent_province`. Joint holdings can
  apply that bonus through the bundled adjacency graph; availability remains
  a separate issue.
- `att_bld_eos_mint` has 2,200 commerce wealth, +18% provincial commerce wealth
  and +30% faction trade tariffs. Honga corroborates those figures, but the
  building remains excluded because its upkeep metadata is missing. Tariffs
  require a supplied campaign tariff base; 30% is not 30% of all GDP.

The patriarchal sites are Rome, Constantinople, Alexandria, Antioch and
Jerusalem. Zafar's special slot belongs to the dam, not a sixth patriarchal see.
These site assignments are already implemented from the bundled start-position
templates; this audit does not change them.

## Data needed to close the gaps

1. Export `building_levels` with exact IDs, `only_in_capital`, `faction_unique`,
   `first_in_world_bundle`, `religion_requirement`, `resource_requirement`,
   `upkeep_cost`, and primary-slot building requirements. This unlocks a per-ID
   rule set and can supply the eight missing upkeep records.
2. Export `building_chain_availabilities`, `building_chain_availability_sets`,
   `building_chain_to_slots` and `building_level_required_buildings`. Join those
   tables to the existing faction, culture and regional slot data; displayed
   names alone cannot validate constructibility.
3. Export the effect bundles referenced by first-in-world rewards and the dam
   event/repair scripts. Preserve their scope and conditions. A one-time reward
   must not become recurring income.
4. Supply the scenario's faction capital and decide how already-built/captured
   special buildings are represented. A current-capital construction condition
   cannot safely be replaced by a universal ownership cap.
5. Validate an ERE/WRE multi-province holding with and without access to its
   actual capital, plus a Celtic adjacent-market case and a Himyar dam case.
   Only then should campaign rankings claim those rules are covered.

The schema source is pinned to a repository revision. TW Database's existing
metadata advertises Steam build **25370302**; Honga and the mod descriptions do
not identify a game build. The local TSV exports also do not establish a matching
build. This audit preserves those distinctions instead of labelling all sources
as one verified vanilla version.

Rebuild and verify offline:

```sh
uv run --frozen python -m games.tw.attila.tools.audit_specials
uv run --frozen pytest tests/games/attila/test_special_audit.py --no-cov
```

The JSON source snapshot records factual observations, source URLs and SHA-256
hashes of retrieved responses. Full third-party pages are not bundled. Rebuilding
the report makes no network requests and does not refresh or modify source data.
