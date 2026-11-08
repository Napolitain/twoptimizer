# Rome II reference income optimizer

Runs without installed game files. Maximizes **current domestic tax receipts less
modeled building maintenance** for all 36 playable Grand Campaign factions,
including Kush, Masaesyli, Nabataea and Saba.

```sh
.venv/bin/python -m games.tw.rome2.benchmark --layout coastal --seconds 12
.venv/bin/python -m games.tw.rome2.benchmark --province Italia --province Africa \
  --province Aegyptus --seconds 15
.venv/bin/python -m games.tw.rome2.benchmark --faction rom_rome --layout coastal \
  --algorithm cp-sat --algorithm cbc --algorithm scip --algorithm scip-nonlinear
.venv/bin/python -m games.tw.rome2.benchmark --layout coastal --all-technologies
.venv/bin/python -m games.tw.rome2.summarize
```

By default the optimizer runs to an optimality/infeasibility proof with no time
cap. `--seconds` enables an optional per-case limit. The portfolio starts with a
short CP-SAT search, then passes an independently validated layout to native
nonlinear SCIP for an uncapped proof search. With an explicit limit it allocates
35% to the first stage. It keeps the best income and tightest
valid bound. `OPTIMAL` requires a solver proof; agreement alone is insufficient.
CBC, OR-Tools SCIP and CP-SAT use exact integer linearization. Bounds respect
the one-level-per-branch rule; additional slot/branch product constraints
strengthen the relaxation. Native nonlinear SCIP retains integer products.
Currency uses 1/10,000 units. The original native model remains the canonical
identity for portable proofs; returned layouts are independently evaluated.

## Sources and corrections

[The catalog](data/economy_catalog.json) includes 1,140 buildings, 36 faction trees,
original raw effect IDs/scopes, traits, research, costs, URLs and response hashes.
The original 32 placement trees use the official archive; four later factions use
Honga rosters. Sixty additional faction-specific raw variants recover temples
and other Desert Kingdoms buildings omitted by the public index; individual pages
provide their displayed effects and costs. Sixteen later spice settlements also
supplement the older archive. Other-campaign prefixes are filtered before merging.

All 1,140 buildings were compared with individual Honga pages in the
[source audit](../../../reports/rome2-source-audit.json). There are 118 catalog
display mismatches and six current displayed-fact mismatches: three Melqart
industry bonuses are conditional edict effects in the raw tables; three Marib
Dam displays say agriculture while the raw ID specifically targets farming.
Raw IDs/scopes remain authoritative for this declared model. Matching displayed
numbers does not prove matching recipient scopes.

**A previous model error was corrected:** `rom_building_food_reserves` is displayed
as food production, not storage. It now contributes to food. Checked-in comparisons
have been rerun; old Rome II results in Git history are superseded. Older official
grain-settlement displays also conflict with raw per-region food; raw scopes stay.
Later imports retain earlier results only when both compiled models are identical
and the stored layout passes evaluation against the new data; report migration
metadata records these checks. Changed problems are solved again.

The raw dump has no installed-build manifest. Archived official pages, public pages
and community references are **not certified as a single current patch**. New
Pantheon/Jupiter rules are outside this profile. An anonymous official Assembly Kit
download was attempted; Steam denied access to Rome II app 267180.

## Research

Research bonuses are disabled by default. Buildings remain mature/unlocked; this
is a controlled comparison, not a historical zero-research campaign. Explicit
`--all-technologies` compares 29 factions with no detected public tree gaps.

Public trees are incomplete for Armenia, Parthia, Rome and the four Desert Kingdoms
factions. Roman Seed Selection's detail page is unavailable; the other six have
visible empty research branches. Explicitly requesting their full public research
fails. `--technology-profile archived` deliberately selects an older profile for
the original 32 factions, never an automatic fallback. Coverage and scoped facts
remain inspectable. `--no-technologies` explicitly selects the default baseline.

## Provinces and regional bonuses

[world.json](data/world.json) assigns resources to all 173 regions in 57 provinces.
The community source declares patch 18. Every identity and capital flag matches
repository tables. Three port conflicts (Apollonia, Larissa, Hecatompylos) retain
repository templates. The reader extract records source lines and capture method;
its hash is not presented as an HTTP response hash.

[world_modifiers.json](data/world_modifiers.json) records 14 economic bonuses,
including Roma, Carthago, Pergamon, Antioch and natural wonders. Province bonuses
stay local; faction bonuses require ownership of their source region. Each named
province comparison owns that province alone. Conditional Bread and Games effects
stay inactive. Conflicting older 2013 wonder values remain visible.

Roma's all-income bonus is interpreted as additive all-source wealth; Pharos'
sea-trade bonus as maritime wealth. These two interpretations still need effect
definitions. `--no-world-bonuses` gives a resource-only sensitivity. Named holdings
are counterfactual equal-holding comparisons, not historical starts or empire totals.

## Enforced rules and remaining scope

- Nine wealth categories distinguish farming, livestock, entertainment, learning,
  manufacturing, mining, local commerce, maritime commerce and subsistence.
  Wealth modifiers add before tax multiplies modified wealth. Epirus' minor-site
  bonus applies only to wealth originating in minor settlements.
- Tax modifiers/corruption deductions are percentage points. Corruption reductions
  cannot make corruption negative. Food and province public order must be nonnegative.
  Per-region food counts once per owned recipient; adjacent provinces are unowned.
- One primary per site, one port where coastal, four ordinary capital plots and
  two ordinary town plots. Mature primaries up to level four and ordinary levels
  1–4 are used; shorter resource chains stop at their actual maximum (e.g. iron).
  Public placement rules distinguish city/town, major-only sanitation and industry,
  and minor civil agriculture/mining. Installed `building_sets` validation remains.
  Duplicate stages of a branch cannot coexist; distinct upgraded branches may.
- One playable political profile is selected; family effects are not stacked.
  Safely dominated profiles can be pruned for this objective.
- Marib Dam is restricted to Marib. Its raw farming modifier is retained and
  maintenance is deducted once, outside the tax multiplier.

Hypothetical inland/coastal/grain layouts each contain one capital and one town;
grain changes the minor primary. `Scenario`/`Site` accepts custom slot capacities,
tax, corruption, public order, external food and explicit sourced modifiers.

Default corruption/slaves are zero; own culture is 100%. Construction resources
and unlocks are available independently of research bonuses. There are no active
edicts, faction-capital-only subsistence, external trade/export/tariff receipts,
armies, agents, construction spending, treasury interest, difficulty, imperium,
character/event modifiers or future cash-flow timeline. Growth is reported without
future value. Level-5 special monuments are excluded. This is a static domestic
income model, not exhaustive campaign economics.

## Results and replay

[Rankings](../../../reports/rome2-ranking.csv) combine incumbents and upper bounds,
keeping scenarios and research modes separate. Rank intervals preserve uncertainty.
Reports contain original layouts, categories, food/order, maintenance, hashes and
timing. Identical compiled CP-SAT models may reuse an optimum; receiving layouts
are independently checked. Resume rejects different data/model snapshots.

The checked-in coastal benchmark proves all 36 cases without research bonuses:
Nabataea and Saba tie at 4,477.248. All 29 supported public research cases are also
proved; Carthage leads that subset at 7,312.68 (Rome and six other incomplete
research profiles are excluded). Named provinces provide 108 feasible layouts,
with three proved optima; their faction rankings retain intervals. These are
model results, not installed-game certification. All 188 saved layouts across
the comparison reports passed independent replay. The regression suite has
251 passing tests.

```sh
.venv/bin/python -m games.tw.rome2.import_data
.venv/bin/python -m games.tw.rome2.import_public
.venv/bin/python -m games.tw.rome2.world
.venv/bin/python -m games.tw.rome2.audit_sources --download
.venv/bin/python -m games.tw.rome2.verify
```

Importers/audit support cached `--offline` replay; the world join uses its checked-in
factual extract. Re-run benchmarks after data/model changes. All five solver modes
are tested against exhaustive small-layout enumeration. Regression checks cover
food, corruption, maintenance, warm starts, source parsing and geography joins.
`--resume --fill-missing` continues interrupted batches without spending another
budget on already feasible cases. Plain `--resume` improves unresolved cases.
