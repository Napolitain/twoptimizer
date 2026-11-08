# Shogun 2 domestic income optimizer

This model optimizes **current provincial tax receipts**, in koku per turn,
using public encyclopedia records and explicit scenario inputs. It can run
without an installed copy. It is not an exhaustive campaign simulator or a
claim to have verified the current patch.

```sh
.venv/bin/python -m games.tw.shogun2.benchmark
.venv/bin/python -m games.tw.shogun2.benchmark --soil native \
  --algorithm cp-sat --algorithm cbc --algorithm scip
.venv/bin/python -m games.tw.shogun2.benchmark --clan chosokabe \
  --province jap_owari --province jap_settsu --town-wealth 1000
.venv/bin/python -m games.tw.shogun2.benchmark --clan oda --province all --joint --soil native
.venv/bin/python -m games.tw.shogun2.benchmark --clan oda --province all --independent --soil native
```

The default compares all 12 playable clans with joint ownership of Sado,
Settsu and Owari. Sado has barren soil and gold; Settsu has average soil and
philosophical tradition; Owari has very fertile soil. Two sensitivity cases
replace every province's soil multiplier with barren (1) or very fertile (3).
The default solver is CP-SAT and runs to completion without a time cap.
`--seconds` explicitly enables an optional per-case time limit.
`--joint` is the default; `--independent` solves each selected province separately.
`--province all` selects all 65 provinces. Independent cases reset faction food
and unique-building limits: their individually optimal layouts cannot generally
be added into one legal faction holding. JSON retains every solver case; CSV
retains one row per clan, soil and holding, with explicit ownership and province IDs.

## Enforced mechanics

- Exactly one castle and farm per province, with dedicated road, port and
  specialty plots where available. A castle's level provides 1–5 ordinary
  town-building slots. Each town chain occupies at most one slot.
- Specialty buildings only at their corresponding resource locations; ports
  only on port sites. Native religious chains are used, including Otomo's
  Hospital/Jesuit branch instead of the Mission/Church/Cathedral branch. Nanban contact is off
  in the default comparison; the Python scenario API supports it explicitly.
- Shared faction food must be nonnegative. Castle and market consumption
  compete with farm production. Chonindo's +2 and Sumo Tournament's -1 apply
  once to the faction, not once per province.
- Local public order must be nonnegative. The default supplies normal-tax
  unrest of -4 and assumes 100% adherence to the clan's state religion.
- At most one newly constructed legendary town building per chain per faction,
  including Kabunakama, Mizu Shobai and the Famous Temple. The Nanban chain
  also has a faction-wide limit. Jesuit Colleges are regular buildings and do
  not have a legendary limit. Captured duplicates are outside this scenario.

Regional specialties cover all 11 imported types: craftwork, gold, holy sites,
horses, intellectual centres, iron, naval tradition, ninja, smithing, stone and
timber. Their buildings are available only at the sourced locations. Income,
tax and order effects stay local: for example, Settsu's Law Court does not add
its tax bonus to Sado. Arts supply the sourced clan-wide tax, farm and order
bonuses to every owned province, while arts food enters the faction total once.

The catalog's 15 neighboring-province building effects are **religious zeal**.
They are recognized and reported as excluded conversion dynamics; they are not
direct tax or wealth bonuses. This static model assumes 100% state-religion
adherence and does not invent adjacency income. Naval specialties' tariff
bonuses and legendary buildings' first-construction military/agent rewards also
remain explicitly outside current domestic taxation. Joint ownership still
matters because food and legendary-building limits are shared across the holding.

The income formula is:

```
farm wealth = selected farm yield × soil multiplier × (1 + farm bonuses / 100)
taxable wealth = supplied town wealth + farm wealth + commerce + mining
tax rate = supplied base rate + arts tax points + local building tax points
tax receipts = taxable wealth × tax rate / 100 × supplied administration multiplier
```

Chosokabe adds 10% farm wealth; Equal Fields adds another 2%. The imported
arts provide 8 tax points in total. Arts are assumed researched, and all
construction-resource prerequisites are assumed accessible. There is no
construction budget, build sequence or historical starting layout.

All clans receive the same fixed starting town wealth (zero by default),
30% base tax and administration multiplier 1. These are controlled inputs,
not an inferred historical campaign state. Positive town wealth and different
effective tax rates can be supplied. The Python `Province` API also accepts
administration and order offsets, which must include any additional effects
the scenario needs.

## Results and practical limits

The checked-in [CSV](../../../reports/shogun2-income-comparison.csv) and
[full report](../../../reports/shogun2-income-comparison.json) contain 36
clan/soil cases, each solved with CP-SAT, CBC and SCIP. Every solver proved
optimal and agreed with the other two. Selected layouts are independently
checked against the original economic formulas and constraints. A reduced
model is also checked by exhaustive enumeration in the test suite.

The default native-soil holding generates 7,948.36 koku/turn for Chosokabe,
7,688.06 for the other Buddhist clans, and 6,345.81 for Otomo and Ikko Ikki.
Chosokabe benefits from farm wealth. Buddhist clans can construct the
Famous Temple's +25 tax-point building; the native Christian and Ikko chains
lack that modifier. This ranking excludes external trade and military spending,
so it does not rank a clan's complete campaign economy.

Town growth from buildings, arts and each point of shared food surplus is
reported separately. It does not contribute to the current-income objective.
Tax-induced growth penalties, religious conversion, population/wealth dynamics,
governors, metsuke, events, difficulty, first-construction race rewards,
diplomatic trade flows, the common clan stipend, military expenses and future
cash flow are not simulated. Tied income layouts can have different
growth. Portuguese land-leasing cash is a one-off and is excluded from recurring
wealth. Uesugi's trade trait is outside the domestic-tax objective. Construction
cost and tariff facts are recognized but not valued by this objective.

The report preserves recognized facts, their disposition, excluded clan traits,
other out-of-scope facts, source-file hashes, bounds and solver timings. An
`OPTIMAL` status proves the stated mathematical model; it does not certify
that every game rule has been imported.

## Sources and reproducibility

- [Mirrored official buildings and arts](https://liquidwork.github.io/shogun2-encyclopedia/buildings.html):
  115 building records and 45 arts in the shared public catalog.
- [Province index](https://shogun2-encyclopedia.com/regions.html):
  all 65 soils, port sites and specialty locations. The importer explicitly
  maps its `Kozuka` spelling to the archived catalog's `Kozuke`. Narrative
  specialty yields sometimes conflict with structured records, so only
  locations/soil are taken from that index.
- [Official food rules](https://liquidwork.github.io/shogun2-encyclopedia/how_to_play/019b_enc_manual_food_shortages.html)
  and [construction rules](https://liquidwork.github.io/shogun2-encyclopedia/how_to_play/018e_enc_manual_actions_campaign_construction.html).
- [Economy guide and starting-state examples](https://steamcommunity.com/sharedfiles/filedetails/?id=2215397548):
  numeric Chosokabe farm modifier; the source also provides examples of
  fertility-scaled farm wealth.

Additional references for fertility multipliers, additive tax points and unique
buildings are retained in [rules.json](data/rules.json). Downloaded rule pages
have URLs, byte counts and SHA-256 hashes. The importer fails on unknown
province identities, fields or specialties instead of guessing.

```sh
.venv/bin/python -m games.tw.shogun2.import_rules
.venv/bin/python -m games.tw.shogun2.import_rules --offline
```

The shared public catalog has its own cached importer. Installed exports will
let us verify patch differences, availability, effect scopes and starting
state. They are a validation step, not a prerequisite for this declared static
optimization.

### Campaign map and adjacency

[campaign_map.json](data/campaign_map.json) includes all 65 Sengoku provinces
and 103 explicit `CAI_REGION_BOUNDARY` links, including Sado as an isolated
province in this graph. The same graph, boundary codes, distances, AI IDs and
coordinates were extracted from two public calendar-mod packs: an older
build-5890 campaign and a Complete Edition conversion. The newer mod documents
its change as the number of turns per year. Both pinned repository revisions,
pack hashes, extracted campaign hashes, build strings and parsing references
are retained in [campaign_adjacency_source.json](data/campaign_adjacency_source.json).

The source boundary codes are preserved: 101 links have code `0`; Awa–Awaji and
Buzen–Nagato have code `1`. Those two pairs geographically correspond to strait
crossings, but the enum's meaning has not been independently documented, so no
movement or bonus-propagation semantics are inferred from it. All 103 explicit
source links are retained in the province graph.

The province index separately supplies 3,107 exact display-polygon points and
centroids, with source URL/hash and image dimensions.
[campaign_map_source.json](data/campaign_map_source.json) preserves these fields.
Both bundled extracts support deterministic offline regeneration:

```sh
uv run --locked python -m games.tw.shogun2.import_map --offline
uv run --locked python -m games.tw.shogun2.import_map
```

Offline replay validates the captured boundary checksum against both recorded
source digests. The adjacency input is an audited capture; raw-pack decoding
is a separate audit using the referenced external parsers.

The second command refreshes display geometry from the online index or cache
and retains the bundled, pinned adjacency extract. No borders are inferred from
polygon proximity. `coverage.complete` and `coverage.geometry_complete` describe
complete coverage of this source campaign, not verification against the user's
installed build. The source packs are mods; neither is a directly inspected
vanilla installation. Sea regions/routes, hidden bases, pathfinding obstacles
and other campaigns remain outside this province graph. Display centroids and
engine AI positions are separate fields, neither claimed as settlement positions.
The map does not change the income model's treatment of neighboring religious
conversion or prove which effects propagate across each boundary.
