# Rome II reference income optimizer

This optimizer runs without installed files, combining the repository's raw
Rome II effects and slot tables with online building eligibility, faction-specific
technology trees and faction traits. It maximizes **current domestic provincial
tax receipts**, not treasury growth or complete campaign profit.

```sh
.venv/bin/python -m games.tw.rome2.benchmark --layout coastal --seconds 15
.venv/bin/python -m games.tw.rome2.benchmark --layout coastal --seconds 60 --resume
.venv/bin/python -m games.tw.rome2.benchmark --faction rom_rome \
  --layout coastal --algorithm cp-sat --algorithm cbc --algorithm scip
.venv/bin/python -m games.tw.rome2.benchmark --faction rom_arverni \
  --layout coastal --algorithm scip-nonlinear --seconds 30
```

`python -m games.tw.rome2.main` now routes here, replacing the unfinished prototype.
`pyscipopt` supplies the native nonlinear SCIP formulation.

## Imported data and limits

The [supplement](data/economy_catalog.json) includes 894 buildings, 32 playable
Grand Campaign faction trees, 2,077 faction/technology records, 173 region
identities with port/capital/slot metadata, and 57 provinces. Source URLs, hashes,
original effect IDs/scopes, culture-specific names and costs remain inspectable.

The importer filters Grand Campaign occurrences before merging building IDs.
This avoids the mixed-campaign religious rosters in the shared public catalog.
It preserves faction-specific temples, rejects conflicting official numeric
records, decodes map JSON without executing scripts, and joins exact region IDs
to the raw slot templates. Missing raw economic rows cause a failure.

The repository dump lacks an installed-build manifest. The official encyclopedia
is an older Emperor Edition snapshot; Honga faction traits can reflect later
patches. **Their combination is not certified as a uniform/current patch.**
New Pantheon/Jupiter campaign changes are outside scope. Four later playable
faction trees absent from the official source are explicitly excluded.

Complete resource-to-region assignments, numeric natural-wonder bonuses and
historical campaign state remain unverified. The benchmark uses explicit
controlled holdings instead of inventing those inputs:

| Layout | Provincial capital | Minor settlement |
| --- | --- | --- |
| Inland | Four ordinary plots, no port | Two ordinary plots, no resource, no port |
| Coastal | Four ordinary plots, port | Two ordinary plots, no resource, port |
| Grain | Four ordinary plots, port | Two ordinary plots, grain core, port |

Each site also has a separate compulsory primary; coastal sites have a separate
compulsory port. These are independent hypothetical realms, not simultaneous
holdings or historical starting provinces. The `Scenario`/`Site` Python API accepts
other site counts, slot capacities, port sites and resource assignments. Imported
geography can support later validated historical scenarios; an omitted resource
assignment is not evidence that a historical region has no resource.

## Enforced economics

- Nine wealth categories distinguish farming, livestock, manufacturing, mining,
  entertainment, learning, local commerce, maritime commerce and subsistence.
  Applicable province/global/category bonuses add to 100%, then multiply base
  category wealth. Epirus' displayed minor-settlement modifier applies only to
  wealth originating at minor sites; its exact effect definition needs validation.
- Normal taxation turns 100% of modified wealth into income. Tax bonuses and
  supplied corruption deductions change that factor by percentage points.
- Food is shared. Local output counts once; effects delivered to every owned
  region count once per recipient. Adjacent-province effects have no recipients
  in a single-province realm. Food must be nonnegative.
- Squalor and sanitation happiness directly affect provincial public order,
  which must be nonnegative. Attila's sanitation constraint and Shogun 2's
  food-growth rule are not copied into this model.
- One primary per site, one port per coastal site, and ordinary slot capacities
  are enforced. Placement distinguishes city/town centres, major-only sanitation,
  tax and industry, and minor civil agriculture/mining. Those reconstructed rules
  still need installed `building_sets` validation. Different upgraded branches
  may coexist; repeated levels of the same branch may not.
- Exactly one playable political profile is selected. Families are not stacked.
  The default chooses the best profile for this objective; safely dominated
  profiles can be removed. Reports preserve source indices and facts because
  reliable party-name IDs are absent. This represents choosing a campaign profile.

The benchmark assumes all imported technology effects, accessible construction
resources/unlocks, level-4 primaries and ordinary levels 1–4. `--no-technologies`
removes research effects while retaining the declared mature/unlocked scenario.
Level-5 special monuments and their location/uniqueness conditions are excluded.

Default corruption and slaves are zero; own culture is 100%. Culture-order
bonuses use the displayed maximum. There are no armies, garrisons, neighboring
wars, edicts, difficulty/imperium/character offsets, natural-wonder bonuses or
faction-capital-only subsistence. External trade/export/tariff receipts, military
and agent expenses, construction spending, treasury interest and events are
excluded. Growth is reported but no future wealth, queue or cash-flow timeline
is simulated. Conditional edict/slave facts remain visible in the audit.

## Solver evidence

CP-SAT uses exact integer products. CBC and OR-Tools SCIP use exact mixed-integer
linearization; native SCIP uses nonlinear constraints. Currency is calculated
in 1/10,000 units, without coefficient rounding. Each returned layout is separately
evaluated against original economics, placement, slots, food, order and party choice.
All four formulations are checked against exhaustive enumeration in a small model.

The [combined ranking](../../../reports/rome2-ranking.csv) uses each solver's
best incumbent and tightest upper bound. Rank intervals preserve uncertainty.
In the coastal reference holding Rome's 9,973.165 and Carthage's 7,337.4 are
proved optima and their first/second ranks are certified against all other
imported factions' bounds. With a grain core, their proved income becomes
10,793.115 and 8,498.42; only those two factions are compared in that sensitivity.
These are results of the declared reference model, not current campaign rankings.

```sh
.venv/bin/python -m games.tw.rome2.summarize
```

The [income report](../../../reports/rome2-income-comparison.json) and
[CSV](../../../reports/rome2-income-comparison.csv) preserve layouts, category
breakdowns, bounds, times, source/model hashes and an effect audit. `OPTIMAL`
means a proof for this reference model; `FEASIBLE` retains a gap. Agreement
between solvers alone is not an optimality proof. The
[solver comparison](../../../reports/rome2-solver-comparison.csv) covers
representative Roman, Punic and barbarian cases; no backend universally wins.

Identical compiled CP-SAT models may reuse an optimum. Hashing removes variable
names while retaining domains, constraints and objective coefficients. Receiving
layouts are independently evaluated and reuse is disclosed. Resume checks both
data and model-source hashes before accepting old proofs.

```sh
.venv/bin/python -m games.tw.rome2.import_data
.venv/bin/python -m games.tw.rome2.import_data --offline
```

Sources: [official building trees](https://r2encv2.totalwar.com/en/buildings/),
[technologies](https://r2encv2.totalwar.com/en/technologies/),
[region map](https://r2encv2.totalwar.com/en/regions/),
[wealth rules](https://r2enc.totalwar.com/en/manual/single-player/0044a_enc_page_campaign_play_province_wealth/),
and [Honga factions](https://www.honga.net/totalwar/rome2/faction.php?l=en).
Installed exports will let us verify patch, availability, scope and world-state gaps.
