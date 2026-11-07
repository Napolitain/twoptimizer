# twoptimizer

Total War economic optimization and HoI4 experiments. Smite 1 and 2 have been
removed. The HoI4 module is retained for a separate redesign.

## Run Attila

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m games.tw.benchmark --province Thracia --fertility 5 \
  --seconds 60 --output benchmark-results/thracia.json
```

The default solver is native CP-SAT. The default scenario uses Eastern Roman
Empire buildings, Orthodox religion, level-4 cities, all available nonmilitary
building levels, and all technologies unlocked. Without `--province`, the runner
covers all 62 map provinces at fertility 0 and 5; these are hypothetical owned
provinces, not the faction's starting territory.

The JSON contains selected buildings and per-region wealth, food, sanitation and
fertility; province public order; solver status, objective and bound; data
fingerprint; and an explicit list of unmodeled effects. Auxiliary product variables
are excluded from the building list. Every candidate layout is checked against
the compiled constraints and the separate layout evaluator.

`OPTIMAL` means the solver proved the optimum of this stated model. `FEASIBLE`
means an incumbent was found with a remaining bound; `INFEASIBLE` is a proof that
the selected requirements cannot all be met. `UNKNOWN` means the time budget
expired without a usable result. No result is labeled optimal just because it
matches another algorithm's score.

### Objectives and scenarios

* `--objective wealth` (default): maximize building-generated wealth, including
  additive category and all-wealth percentage bonuses.
* `--objective income`: apply building tax-rate modifiers at a neutral baseline
  tax multiplier of 1, then subtract imported building upkeep. This is a static
  building-income proxy, not a complete treasury forecast. It creates a larger
  model; allow more time than for wealth.
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
No technology arguments means all technologies are available. Requirements stay
specific to the culture. Missing metadata raises an error when a requested
restriction cannot be checked; it is never interpreted as a free building.
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
  Adjacent-province effects require an explicit adjacency mapping; conditional
  food-sharing effects remain unmodeled until their condition is supplied.
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
solve budget is 60 seconds with one worker. LP/MPS exports remain available.

## Refresh the online data

No installed game is needed for the checked-in snapshot or the online importer.

```sh
.venv/bin/python -m games.tw.attila.tools.import_online
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
food and public order and at least one net sanitation point per region. It does
not simulate construction queues, upgrade histories, treasury budgets, growth,
religious unrest, governors, external technologies' economic bonuses, corruption,
trade agreements or campaign food imports. Imported construction costs/times are
catalog facts, not a construction schedule. City capacity still follows the
existing level-4 slot assumptions; lower-city scenarios need further validation.
Immigration-related modifiers and conditional food-sharing effects are reported
rather than assigned invented inputs. Additional campaign mechanics and data
validation are still necessary before calling this a full game simulation.

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
unchanged. The default remains one worker for reproducible comparisons.
