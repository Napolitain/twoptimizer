# twoptimizer

Game optimization experiments. Total War: Attila includes checked-in building
and map tables, so its existing static province GDP model can be benchmarked
without an installed copy of the game.

The Total War engine now defaults to native CP-SAT (`Problem()`), including the
Attila entry point (`python -m games.tw.attila.main`). CBC remains available as
`Problem(solver=SolverType.GOOGLE)`, SCIP as `SolverType.SCIP`, and the previous
PuLP backend as `SolverType.PULP`. Import `SolverType` from `games.tw.enums`.
CP-SAT uses a 60-second solve budget and one worker by default. Its status and
bound are available through `problem.problem.result`; failure to find a feasible
layout raises an error instead of exposing an invalid objective. LP/MPS dumps
still export the original linear model.

## Compare Total War algorithms

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m games.tw.benchmark --output benchmark-results/attila.json
```

The default runs all 62 provinces at fertility 0 and 5, using Eastern Roman
Empire buildings, Orthodox religion, minimum city/building level 4, and no
military buildings. These match the existing Attila regression settings.
The faction determines available buildings; the province list covers the map,
not only that faction's starting territory.

For a smaller run or different settings:

```sh
.venv/bin/python -m games.tw.benchmark --limit 3 --seconds 1
.venv/bin/python -m games.tw.benchmark --province Thracia --fertility 1.25 5 \
  --algorithms cbc cp-sat beam glop --output benchmark-results/thracia.json
.venv/bin/python -m games.tw.benchmark --help
```

| Algorithm | Method | Guarantee |
| --- | --- | --- |
| `cbc` | CBC mixed-integer branch-and-cut | Optimal if status is `OPTIMAL`; otherwise reports an incumbent when available |
| `scip` | SCIP mixed-integer optimization | Same; reports `UNAVAILABLE` if absent from the OR-Tools build |
| `cp-sat` | Native CP-SAT with exact decimal integer scaling | Optimal if proved; refuses unsafe coefficient magnitudes |
| `greedy` | LP-guided construction, retaining one partial layout | Feasible solutions only; can miss a feasible layout |
| `beam` | LP-guided beam search with resource penalties and interval pruning | Feasible solutions only; default beam width 128 |
| `multistart` | Beam search with seeded shuffled orders, followed by feasible flips/swaps | Feasible solutions only; default 16 attempts |
| `glop` | Continuous relaxation of the same binary model | An optimal LP objective gives an upper bound, not a building layout |

Each case snapshots the engine's filtered binary model once. All algorithms use
those same GDP coefficients, building restrictions, slot/chain limits, mandatory
cities/ports/resources, food, public order, and cross-region sanitation constraints.
Every returned solution is checked against the original snapshot. CP-SAT scales
each row and the objective separately without rounding decimal coefficients.

The table reports objective, status, elapsed time, and gap to the tightest available
solver/LP upper bound. JSON also includes chosen building IDs, fractional LP
values, gap to the best observed feasible layout, settings, OR-Tools version, and
a SHA-256 fingerprint of the source TSVs. A heuristic failure is
`NO_SOLUTION_FOUND`, never a proof of infeasibility. A zero observed gap does not
change a heuristic's status to `OPTIMAL`.

`--seconds` sets a per-algorithm budget, including its private model construction
and LP guidance. Limits are cooperative: native solver shutdown, validation, and
an in-progress search operation can add small overhead. Shared engine snapshot
time is recorded separately. CP-SAT uses one worker and a fixed seed; elapsed
times depend on the machine and solver versions. For performance conclusions,
repeat runs under the same configuration. Beam truncation can lose solutions;
increasing `--beam-width` or `--restarts` trades time for search coverage.

These comparisons optimize the existing static model, not construction schedules
or an independently validated simulation of the game. Existing parser limitations,
including ignored/unsupported effects, are inherited by every competitor. Rome II
is not included in this runner because its checked-in data lacks the province and
region name tables required by the current parser.

Run the optimization checks with:

```sh
.venv/bin/python -m pytest tests/test_tw_competition.py tests/test_attila_regions.py
```

The new checks compare against exhaustive enumeration on small mixed-sign binary
models, verify fractional LP bounds and infeasibility reporting, and compare native
CP-SAT against the saved Attila engine results.

## Measured comparison

A single run in this workspace used `--seconds 1`, default beam width/restarts,
and all 62 provinces at fertility 0 and 5 (124 cases), with OR-Tools 9.15.6755.
All three exact solvers proved the saved regression optimum on every case.

| Algorithm | Feasible layouts | Matched optimum | Median total time |
| --- | ---: | ---: | ---: |
| CBC | 124/124 | 124/124 | 52.69 ms |
| SCIP | 124/124 | 124/124 | 221.04 ms |
| CP-SAT | 124/124 | 124/124 | 32.20 ms |
| LP-guided greedy | 114/124 | 0/124 | 5.65 ms |
| LP-guided beam | 124/124 | 23/124 | 23.50 ms |
| Multistart + local improvement | 124/124 | 55/124 | 285.25 ms |
| GLOP relaxation | Fractional | Upper bound only | 1.86 ms |

CP-SAT is the strongest default on this measured dataset. Timings are from one
run, not a repeated performance study. The generated, git-ignored
`benchmark-results/attila.json` contains layouts and per-case evidence;
`benchmark-results/attila-summary.csv` contains a compact comparison.
