# twoptimizer

Total War economic optimization and HoI4 experiments. Smite 1 and 2 have been
removed. The HoI4 module is retained for a separate redesign.

[Shogun 2, Rome II and Three Kingdoms data preparation](games/tw/multigame/README.md)
includes public reference catalogs, a coverage audit and an installed-game
TSV ingestion command. **Shogun 2 now has a public-data domestic-tax optimizer**
and [12-clan results](reports/shogun2-income-comparison.csv).
**Rome II also has a working public-reference optimizer** and
[36-faction comparisons with rank bounds](reports/rome2-ranking.csv), including
named provinces with sourced resources and regional bonuses.
Three Kingdoms has [583 audited building detail pages](reports/three-kingdoms-readiness.json)
but still lacks essential rules for a trustworthy optimizer. Neither new model is a complete
installed-build-verified campaign simulation.

## Interactive terminal UI

Install once, then launch without parameters:

```sh
python -m venv .venv
.venv/bin/pip install -e .
.venv/bin/twoptimizer
```

From the repository, `.venv/bin/python -m twoptimizer` opens the same TUI after
installing `requirements.txt`. The existing CLI commands below remain available.

![Interactive terminal workbench](docs/tui.png)

The Textual interface supports Attila, Rome II and Shogun 2. Choose a faction or
all factions, a province, research profile and solver with clickable,
searchable dropdowns. Attila adds fertility/religion; Shogun 2 adds soil, town
wealth and tax; Rome II offers regional bonuses and explicit research profiles.
The default is a Rome II coastal reference case using the CP-SAT/SCIP portfolio.
Runs have **no time limit by default**: they continue until the solver proves
optimality or infeasibility. Cancel remains available. The optional **Use a time
limit** checkbox enables early termination when explicitly requested.
CPU parallelism is automatic: CP-SAT and supported SCIP interfaces use available
CPUs while respecting process affinity and container quotas. Backends without
supported parallel search remain serial. No worker count is required in the TUI;
`--workers` remains an optional CLI override.
Three Kingdoms and HoI4 show their current readiness rather than starting an
unsupported optimization.

- Mouse clicks, wheel scrolling, arrows, Enter and Tab/Shift+Tab navigate the UI.
- **Ctrl+R:** run; **Esc:** cancel the active batch; **Ctrl+Q:** quit.
- **Ctrl+S:** export JSON and CSV; **F1:** keyboard help and model-status meanings.
- Result rows show income, status, bound gap and timing. Click a heading to sort;
  select a row to inspect it, or press Enter to open its building layout.
- Compare exact solvers runs the supported formulations on the same selected
  holding. All-faction research runs explicitly list unavailable profiles.

Solves run in separate processes, so cancellation and exit stop the active solver
while keeping completed results. Exports include scenario settings, source hashes,
assumptions and the original engine result. Reports default to
`benchmark-results/tui/`; the export dialog accepts another filename and protects
existing JSON/CSV files unless replacement is explicitly selected. Model notes
state each game's income definition and remaining data gaps. Values from different
games are not a common GDP ranking.

The status line shows engine startup, data loading, model building, solving and
validation. Finished rows include phase timings; JSON exports also retain solver
conversion/search/validation times. Attila and Shogun 2 exact solvers use sparse
constraints, avoiding a large mostly empty matrix (the ERE/Thracia case drops
from 153.5 MB to 0.49 MB of constraint storage).

The TUI currently configures one province/holding per run. The CLI retains joint
province optimization, campaign JSON inputs and the other existing advanced options.
Installed wheels include the game data; a Git checkout is not required to run them.

The new launcher also forwards CLI arguments unchanged:

```sh
.venv/bin/twoptimizer rome2 --layout coastal --seconds 15
.venv/bin/twoptimizer shogun2 --soil native --algorithm cp-sat
.venv/bin/twoptimizer attila --province Thracia --fertility 5 --seconds 15
.venv/bin/twoptimizer attila-factions --help
```

All optimizer CLIs also run without a time cap by default. Omit `--seconds` to
run to completion; specify it only when you want an optional per-case time limit.

## Run Rome II

```sh
.venv/bin/python -m games.tw.rome2.benchmark --layout coastal --seconds 15
.venv/bin/python -m games.tw.rome2.benchmark --faction rom_rome \
  --layout coastal --algorithm cp-sat --algorithm scip --algorithm cbc
```

The [Rome II model](games/tw/rome2/README.md) uses raw repository effects and
online building/research references. It handles shared food, province-wide
wealth bonuses, public order, distinct primary/port/ordinary plots, resource
cores, faction traits and one political profile. Solver bounds accompany
unfinished proofs. Its reference holdings have explicitly supplied resources
and slots; historical starting worlds and current patch fidelity are not assumed.

## Run Shogun 2

```sh
.venv/bin/python -m games.tw.shogun2.benchmark
.venv/bin/python -m games.tw.shogun2.benchmark --soil native \
  --algorithm cp-sat --algorithm cbc --algorithm scip
```

The [model and assumptions](games/tw/shogun2/README.md) cover jointly owned
provinces, native soils and specialties, castle-dependent town slots, shared
food, local order, religious chains, unique buildings, farm bonuses and tax
modifiers. This is a static current-income comparison with supplied town wealth,
not a full campaign or long-term growth forecast. Public references still need
validation against the installed build.

## Run Attila

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m games.tw.benchmark --province Thracia --fertility 5 \
  --seconds 60 --output benchmark-results/thracia.json
```

The default solver is native CP-SAT. The default scenario uses Eastern Roman
Empire buildings, Orthodox religion, level-4 cities, all available nonmilitary
building levels, all technology effects, and the **income** objective. Technologies
that disable legacy unlocks are respected. Without `--province`, the runner
covers all 62 map provinces at fertility 0 and 5; these are hypothetical owned
provinces, not the faction's starting territory.

The JSON contains selected buildings and per-region wealth, food, sanitation and
fertility; province public order; solver status, objective and bound; data
fingerprint; and an explicit list of unmodeled effects. Auxiliary product variables
are excluded from the building list. Every candidate layout is checked against
the compiled constraints and the separate layout evaluator.
`layout.finances` separates gross wealth, tax bonuses, corruption losses,
building upkeep, trade, tribute/subsidies and recurring net income.
`faction_traits`, `imported_modifiers` and `catalogue_exclusions` expose the
active facts, conditional inputs and missing building metadata.

`OPTIMAL` means the solver proved the optimum of this stated model. `FEASIBLE`
means an incumbent was found with a remaining bound; `INFEASIBLE` is a proof that
the selected requirements cannot all be met. `UNKNOWN` means the time budget
expired without a usable result. No result is labeled optimal just because it
matches another algorithm's score.

### Objectives and scenarios

* `--objective wealth`: maximize building-generated wealth, including
  additive category and all-wealth percentage bonuses.
* `--objective income` (default): apply tax/corruption assumptions and building modifiers,
  subtract imported upkeep, and add supplied trade, tribute and subsidies. Defaults
  use a neutral tax multiplier of 1, zero corruption and no external revenue.
  This is a static income proxy, not a complete treasury forecast. ERE's +8%
  provincial governor tax bonus counts here. Treasury interest is deliberately
  excluded from this objective. Allow more
  time than for wealth.
* `--objective legacy --building-level 4`: reproduce the historical base-GDP
  benchmark with its old effect interpretation and eligibility assumptions.

```sh
.venv/bin/python -m games.tw.benchmark --province Aegyptus --fertility 3 \
  --region-fertility Alexandria=5 --seconds 60 --output benchmark-results/mixed.json
.venv/bin/python -m games.tw.benchmark --province Thracia --fertility 5 \
  --technology 'Roman Ethics' --technology 'State Maintenance' --seconds 60
.venv/bin/python -m games.tw.benchmark --province Aegyptus --fertility 5 \
  --objective income --seconds 60 --output benchmark-results/income.json
```

Technology arguments use the imported display names. Repeated `--technology`
arguments define the researched set; `--no-technologies` defines an empty set.
No technology arguments means all imported technologies are researched, except
legacy technologies disabled by subsequent research. Imported tax, wealth,
corruption and public-order technology effects apply automatically. Requirements stay
specific to the culture. Missing metadata raises an error when a requested
restriction cannot be checked; it is never interpreted as a free building.
In income mode, buildings without imported upkeep/availability metadata are
excluded and listed by name in `catalogue_exclusions`. This is a known coverage
gap, not a claim that those buildings are unavailable in the game. Wealth mode
can still inspect the older, wider roster. The original tables are retained.
Fertility is an explicit scenario input; historical regional fertility has not
been imported or inferred from a modern map.

## Effect handling

`games/tw/attila/effects.py` defines recognized effect kinds and scopes.
`games/tw/attila/economy.py` evaluates and compiles them. Original effect IDs,
amounts and raw scope strings are retained, including effects outside this model.
Unsupported military effects no longer cause an entire building to be deleted.

* Building bonuses affect their producer only; regional bonuses affect the
  specified region; province bonuses affect the appropriate receiving regions.
* Category bonuses affect the matching wealth categories. For example, industry
  bonuses do not boost farming, while commerce bonuses include land and maritime
  commerce where the effect explicitly targets both.
* Wealth-category bonuses stack additively. Products between selected buildings,
  their bonuses, fertility changes and optional tax modifiers are represented
  with exact Boolean-product constraints. Rational arithmetic is used before
  export to avoid floating-point coefficient artifacts.
* Local sanitation applies once to its own region; province sanitation applies
  once to every region. Two canals with +3 local and +4 province sanitation give
  11, 11 and 8 sanitation in a three-region province.
* Province and faction public order contribute once per receiving province,
  rather than once per region. Immigration penalty percentages are not treated
  as flat public-order losses.
* Faction bonuses can affect all owned provinces passed to one `Problem`.
  Adjacent-province effects use the supplied adjacency mapping in a joint problem.
  Conditional food-sharing effects use explicit recipient maps rather than an invented food-import rule.
* Horde structures are excluded from settlement slots. Religious building
  eligibility follows the selected faith.

Imported `source_tree_group` values describe the source's building-tree display;
they are **not exclusivity constraints**. The existing per-branch level exclusions
remain in place, allowing different branches to coexist. Complete building
availability and slot rules still need validation against the running game.

The API defaults to CP-SAT through `Problem()`. Use
`Problem(solver=SolverType.GOOGLE)` for CBC, `SolverType.SCIP` for SCIP or
`SolverType.PULP` for the prior PuLP backend (`SolverType` is in `games.tw.enums`).
`Problem(technologies={...})` restricts technologies.
`Problem(adjacency={province_id: [neighbor_id, ...]})` supplies neighboring owned
provinces; include their decision variables in the same problem. The CP-SAT
adapter exposes its status and bound through `problem.problem.result`; its default
search has no time cap and selects CPU parallelism automatically. Explicit limits remain available
through the backend API. LP/MPS exports remain available.

## Refresh the online data

No installed game is needed for the checked-in snapshot or the online importer.

```sh
.venv/bin/python -m games.tw.attila.tools.import_online
.venv/bin/python -m games.tw.attila.tools.import_factions
.venv/bin/python -m games.tw.attila.tools.import_modifiers
.venv/bin/python -m games.tw.attila.tools.audit_data
```

The importer reads all 11 culture pages at
[TW Database](https://twdatabase.com/attila/buildings). The checked-in snapshot
contains 566 matched building records: construction cost, construction turns,
upkeep, culture-specific technology requirements and normalized numeric economic
observations. No artwork, descriptions or executable code is imported.

Identity matching requires an unambiguous combination of an existing icon key
and building name. Ambiguous entries are listed under `unresolved`, never guessed.
Requirements from different cultures are preserved separately. Conflicting core
metadata is reported and excluded. The importer checks each page's declared game
build and refuses to mix builds. The snapshot declares Steam build 25370302;
the original TSVs have no recorded patch version, so we do not assert they share
that version.

`online_buildings.json` records source URLs, response SHA-256 hashes, import time
and verification status. `effect_audit.json` enumerates every original
(effect ID, scope) pair, its handling status and source comparisons. The current
cross-check has 6,242 matching numeric observations, including percentage bonuses,
and no disagreements for the Eastern Roman culture. Other reported differences
include horde/migration scope contexts; the original effect table is never
silently overwritten.

`online_factions.json` adds 140 Grand Campaign faction entries from
[Honga](https://www.honga.net/totalwar/attila/faction.php?f=att_fact_eastern_roman_empire&l=en).
Ruling-party and shared culture effects are retained separately from opposition
party effects. `online_modifiers.json` adds all 29 playable faction technology
trees and all 14 state religions from [TW Database](https://twdatabase.com/attila/religions).
Those pages declare the same Steam build as the building snapshot; Honga does
not declare a patch version. Their facts are references, not in-game validation.
Both importers cache responses and support `--offline`; unexpected formats fail.

Responses are cached in `.cache/attila-online/` (git-ignored). Replay without
network access with `--offline`. To fetch a fresh source snapshot, choose a new
cache directory:

```sh
.venv/bin/python -m games.tw.attila.tools.import_online \
  --cache .cache/attila-online-refresh
.venv/bin/python -m games.tw.attila.tools.import_online \
  --cache .cache/attila-online-refresh --offline
```

The importer fails if the upstream format changes. Re-run the audit and tests
before accepting refreshed data. These are third-party reference checks, not
in-game validation. The source's game data remains attributable to its owners.
For a future authoritative local export, [RPFM supports TSV export](https://frodo45127.github.io/rpfm/manual/editors/db.html).

## Compare algorithms

```sh
.venv/bin/python -m games.tw.benchmark --limit 6 --seconds 5 \
  --algorithms cp-sat cbc scip --output benchmark-results/comparison.json
.venv/bin/python -m games.tw.benchmark --limit 3 --seconds 5 \
  --algorithms cp-sat cbc scip greedy beam multistart glop
```

All competitors receive the same model. CBC and SCIP solve its integer
linearization; CP-SAT uses exact decimal integer scaling; GLOP solves its
continuous relaxation for an upper bound. Greedy and beam search use LP guidance;
multistart adds shuffled orders and feasible local improvement. Heuristics can
fail to find a solution, and never establish infeasibility or optimality.

Timing includes each algorithm's private model construction and LP guidance.
Shared engine compilation is recorded separately. Budgets are cooperative;
validation and solver shutdown add overhead. Timing is machine- and
version-dependent: repeat runs for performance conclusions.

Earlier measurements in Git history concern the old base-GDP model. They do not
establish performance for the revised scoped economy. Generated results are kept
under the git-ignored `benchmark-results/` directory.

## Scope and validation

This is a static settlement-building optimizer. It enforces nonnegative building
food and public order and at least one net sanitation point per region unless
scenario thresholds specify otherwise. Growth, research, religious influence,
resources and recruitment capabilities can now be targets or weighted preferences;
the model does not simulate their evolution over time. It does not simulate
construction queues, upgrade histories, battles, population conversion, trade
diplomacy or the full campaign economy. Imported construction times remain catalog
facts. City capacity still follows the existing level-4 slot assumptions;
lower-city scenarios need further validation. Script-driven unlocks and several
hidden flags remain unmodeled. The effect audit identifies these explicitly.

The tests cover independently calculated scope examples, stacked sanitation,
category modifiers, fertility interactions, exact Boolean products, exhaustive
small optimization problems, legacy regressions, source format changes, ambiguous
identities, culture-specific requirements, mixed-build rejection and offline
imports. The HoI4 tests remain in the suite. Rome II is retained, but its current
parser still lacks checked-in province and region name tables.

```sh
.venv/bin/python -m pytest -q
```

### Verified run in this workspace

The wealth measurements below predate automatic technology/faction/religion
modifiers and the change to income as the default. They are historical results
for the narrower model, not measurements of the new default.

The revised wealth model was checked over all 124 default cases. The initial
five-second run proved 113 optimal; the remaining 11 were resolved with a
60-second budget. All 124 layouts were validated against the current model.
The verification report records where a bound from a model with additional
culture candidates was reused after validating its layout under stricter
eligibility; those original timings are not presented as fresh-run timings.
See `benchmark-results/attila-verified-wealth.json` and the compact
`benchmark-results/attila-verified-summary.csv`.

A separate fresh six-case comparison used one worker and five seconds per solver:

| Solver | Proved optimal | Feasible, proof incomplete | Median total time |
| --- | ---: | ---: | ---: |
| CP-SAT | 6/6 | 0 | 1.95 s |
| CBC | 4/6 | 2/6 | 3.83 s |
| SCIP | 2/6 | 4/6 | 5.02 s |

These are single-run measurements. CP-SAT remains the default. `--workers 8`
enables its parallel portfolio when useful; other solvers' thread settings are
unchanged. Those benchmarks used one worker for reproducibility; normal runs now
select CPU parallelism automatically, with `--workers` available as an override.


## Campaign options and priorities

Pass `--scenario path.json` to use campaign inputs. The repository contains three
illustrative scenarios; their numbers are example assumptions, not imported
historical starting conditions:

```sh
.venv/bin/python -m games.tw.benchmark --province Aegyptus --fertility 5 \
  --objective income --scenario games/tw/attila/scenarios/campaign-income.json \
  --workers 8 --seconds 60 --output benchmark-results/campaign-income.json
.venv/bin/python -m games.tw.benchmark --province Aegyptus --fertility 5 \
  --scenario games/tw/attila/scenarios/priorities.json --workers 8 --seconds 60
.venv/bin/python -m games.tw.benchmark --joint --province Aegyptus --province Aethiopia \
  --fertility 5 --scenario games/tw/attila/scenarios/joint.json --workers 8 --seconds 120
```

`--joint` puts all selected provinces in one optimization problem. Faction bonuses,
research targets, export revenue and adjacency are then coupled. Faction tariffs
are counted once, not once per province. Without `--joint`, each province is an
independent scenario; inputs that refer to unselected places are rejected.
The API equivalent is `Problem(scenario=...)` with all participating provinces.

The JSON keys are:

| Key | Meaning |
| --- | --- |
| `provinces` | Province IDs mapped to base `corruption_percent` (0–100), baseline `tax_percent` (default 100), nonpositive `immigration_order`, fixed `public_order`/`food`, and `minimum_food`/`minimum_public_order` |
| `regions` | Region IDs mapped to category/all `wealth_percent` bonuses, baseline `immigration_wealth`, fixed `food`/`sanitation`, and `minimum_sanitation` |
| `external_effects` | Fixed governor/edict/technology effects: recognized `effect` ID, raw `scope`, `amount`, and source `region`; these are constants, not selectable buildings |
| `base_tariffs` | Baseline faction tariff revenue, before building tariff modifiers |
| `resource_prices` | Revenue per exported resource unit; used only for the income objective |
| `resource_demand` | Optional export-volume caps; surplus units have no export value |
| `adjacency` | Source province IDs mapped to adjacent selected province IDs; lists are explicit and directed |
| `conditional_targets` | Effect IDs mapped to source-province/recipient-province lists for exceptional food-sharing/neighbor effects |
| `targets` | Minimum required scoped effects: `metric`, `scope`, `target`, `value` |
| `weights` | Optional GDP-equivalent preference coefficients with the same fields; changes the objective to a weighted score |
| `projects` | Fixed future project quotes: `region`, `base_cost`, optional `name`, `sanitation`, `conversion` |
| `project_budget` | Maximum total quoted cost of those future projects under the selected operating layout |
| `campaign` | Optional `province_capitals_held`, `active_trade_routes`, `base_tribute`, `at_peace_with_sassanids`, and explicit `poor_fertility_regions` |
| `faction_traits`, `technology_effects`, `religion_traits` | Booleans, default true; disable individual imported modifier sources for controlled comparisons |

Resource names include wood, wine, iron, lead, leather, marble, olive, salt, silk,
spice, dyes, gem and cloth. Prices and demand are supplied by the scenario; the
optimizer does not invent world-market prices or trade partners.

Corruption modifiers are relative reductions of the supplied base corruption,
not percentage-point deductions: 50% corruption with a -20% modifier becomes 40%.
Relative modifiers stack additively before application to the base value.
Effective corruption is clamped to [0,100]. Tax multipliers cannot become negative.
Immigration order modifiers scale the supplied negative penalty and cannot turn
it into a bonus; immigration wealth modifiers scale the supplied wealth input.
The scenario must supply these baselines because they cannot be derived from
building data alone. Category wealth bonuses from external effects are scoped
through the same evaluator as building bonuses.
`provinces.*.religious_order` supplies a nonpositive religious-unrest baseline;
researched reductions scale that penalty, rather than becoming flat public order.
Project quotes can specify `main_settlement: true` or a `category` of `main`,
`civic`, `agriculture`, `industry`, `religious` or `military`, so imported
construction discounts affect the appropriate future project only.

Construction projects use general construction discounts plus sanitation discounts
when applicable. Conversion projects use conversion discounts. Costs cannot go
negative. These are quotes for **future projects under a selected operating
layout**. They do not establish that the layout could finance or build itself,
and do not simulate a construction order or treasury cash flow.

Examples of metric names are `growth`, `research_percent`, `resource:wood`,
`religion:orthodox`, `osmosis:orthodox`, `agent_enable:spy`, `agent_cap:dignitary`,
`agent_xp:spy`, `recruitment_points`, `recruitment_xp:infantry`, and
`equipment:armour:gold`. The complete set is `METRICS` in `effects.py`.
`scope` is `region`, `province` or `faction`; the `target` is its exact ID
(or `faction`, which may be omitted). Regional effects aggregate over recipient
regions, provincial capabilities over recipient provinces, and global research
and agent caps once per contributing source. Agent recruitment enablement is
Boolean, so two spy-enabling buildings do not enable two distinct spy types.
State-religion influence joins the selected faith; `religion:state` and the
selected faith's specific metric are aliases. Do not weight both unless that
double preference is intentional.

These metrics measure effect totals/capabilities, not time forecasts or battle
outcomes. A research-rate target does not guarantee that a technology finishes
by a date. Religious influence/osmosis targets do not predict future population
shares or unrest. Weighted objectives are labeled `weighted_wealth` or
`weighted_income` in JSON; their scores must not be reported as pure GDP.

Conditional recipients currently support
`att_effect_public_order_base_neighbouring` and
`att_effect_food_production_fertility_neighbouring`. The input declares where the
condition holds; the model does not infer campaign food-routing conditions.
Unknown keys, nonfinite numbers, invalid IDs and unsupported metrics are rejected.
JSON reports include achieved metric targets, corruption, export revenue, project
cost, and the active scenario inputs, alongside the existing regional breakdown.

### Coverage after adding options

The audit distinguishes options from automatically modeled quantities:

| Status | Effect/scope combinations |
| --- | ---: |
| Core modeled economy | 37 |
| Economic scenario options | 8 |
| Scoped metric targets/preferences | 86 |
| Supported with adjacency input | 5 |
| Supported with explicit conditional recipients | 2 |
| Still unmodeled | 10 |
| Outside the settlement model (mostly army/horde) | 65 |

The unmodeled settlement combinations fell from 103 to 10. The remaining entries
include hidden trade-route flags, faction/script mechanics, wall/artillery flags,
imperium and agent-defense mechanics. This expansion does not claim to simulate
those or the 65 army/horde combinations. Run the audit to inspect each exact ID.

The corruption interpretation is corroborated by the [in-game effect tooltip for
Aksumite Monks’ Quarters](https://www.honga.net/totalwar/attila/building.php?b=att_bld_eos_religion_east_church_major_faction_1&f=att_fact_axum&l=en&v=attila), which describes a percentage of the current value.

The three checked-in scenario examples were exercised end-to-end and proved
optimal before automatic campaign modifiers were enabled. The earlier
Aegyptus/fertility-5 wealth result was 18,675 without a scenario. These checks validate the model and its supplied
inputs, not complete in-game fidelity.

## Compare civilizations by recurring income

```sh
.venv/bin/python -m games.tw.faction_comparison --seconds 15 --workers 8
.venv/bin/python -m games.tw.faction_comparison --resume --seconds 60 --workers 8
```

The default comparison covers all 27 settled playable factions in Aegyptus,
Thracia and Germania, with fertility 5, common Orthodox religion, level-4 cities
and researched technology effects. Huns and White Huns are explicitly excluded
because settlement slots cannot represent a horde economy. Migratory factions
are compared after settlement. Each province is an independent hypothetical
holding: the default capital count is the number of selected capitals, not the
faction's historical holdings. `--all-factions` also includes NPC aliases; their
technology profile uses a labeled culture representative when an individual tree
was not imported. Repeated `--province` and `--religion` change the scenario.

The report writes an income table as CSV and JSON with layouts, income breakdowns,
bounds, source hashes, exclusions and unsupported effects. Identical compiled
models can share an optimality proof; every reused layout is validated against
the receiving model. `--resume` reruns unfinished proofs without repeating proved
cases. These are optimums of the declared model, not full campaign rankings.

The checked-in [income table](reports/attila-income-comparison.csv) and
[assumptions and bounds](reports/attila-income-comparison.json) record this run:
81 optimal province/faction cases, with 27 unpriced building variants disclosed.
The full generated layouts are in `benchmark-results/factions/income.json`.

The [fertility comparison](reports/attila-fertility-comparison.csv) reoptimizes
these factions at fertility 5 and 1 and ranks their mean income across the same
three provinces. Its [inputs and proofs](reports/attila-fertility-comparison.json)
record 162 optimal model cases. The fertility-1 Burgundian scenarios explicitly
enable Harsh Sustenance (+15 food per qualifying region); their missing curing
building metadata remains a limitation. Ties share rank, with gaps afterward.

Automatically applied economic traits include ERE tariffs, Garamantian fertility,
desert sanitation, Venedian farming bonuses, removal of farm order/squalor
penalties, other wealth penalties, and
Eastern sanitation per owned province capital. Aksum's trade income modifier is
applied after tariff/export income. Its food bonus needs `active_trade_routes`;
Sassanid tribute needs `base_tribute`; Lakhmid peace income needs an explicit peace
state. Poor-fertility food recipients are explicit because the source does not
give a numeric fertility threshold. Religious unrest and public-order bonuses
depending on religious presence are not inferred from influence points.

Important gaps remain: some unique/legacy buildings lack imported metadata;
some faction scripts and religious-presence effects are unmodeled; starting
territories, governors, edicts, difficulty, trade partners, military expenses,
construction sequences and cash flow require further campaign inputs/modeling.
The audit now includes faction, technology and religion fact coverage alongside
the original building-effect coverage. The solver does not assert exhaustive
Attila simulation.
