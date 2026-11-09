# Attila joint bounds

Eligible joint Attila CP-SAT runs now prepare income bounds from smaller connected
groups before searching the complete holding. On the measured all-province ERE
workload, this produced substantially higher income and tighter bounds within the
same configured solver allowance, with higher wall time and memory use.
The method preserves the requested income objective, provincial food, public
order, religion, adjacency, factionwide bonuses and optional building requirements
in the final model. It does not assume that provinces with similar buildings can
be optimized independently.

## Measured workload

The workload is ERE with all 62 named provinces together, fertility 5, all research,
Orthodox Christianity, automatic map borders and no optional building or religious
constraints. Automatic selection gives four workers on the measured machine.

Baseline and final candidate are production wheels installed outside the checkout
with the same locked dependencies: Python 3.14.9 and OR-Tools 9.15.6755. Each sample
starts a fresh worker and includes startup. The complete case measurements run
serially without simultaneous solver tests or profiling; the candidate runs its
component searches concurrently within the four-worker allocation. Each variant
has two repeats, a 60-second configured solver allowance, a 150-second wall guard
and a 4 GiB worker-memory guard. No warmup sample is excluded. Loading, compilation
and validation account for wall time beyond the solver allowance.

The [raw report](../../reports/attila-joint-bounds.json) records requests, individual
measurements, statuses, source and driver hashes, environment and rejected
experiments. The baseline is revision `0bbea61`; candidate source hashes identify
the measured package. Rounded ranges below cover both runs of each variant.
The gap is `100 * (upper bound - income) / max(1, abs(upper bound))`.

| Metric | Baseline, two runs | Final candidate, two runs |
| --- | ---: | ---: |
| Total wall time | 75.40–76.00 s | 77.85–78.39 s |
| Validated income per turn | 812,700.93–967,795.68 | 1,556,795.65–1,558,999.70 |
| Certified upper bound | 2,131,737.46–2,311,501.44 | 1,642,648.60–1,648,594.42 |
| Remaining gap | 58.131–61.876% | 5.092–5.568% |
| Peak worker RSS | 1,350.94–1,351.24 MiB | 1,578.64–1,591.16 MiB |
| Terminal status | FEASIBLE | FEASIBLE |

Candidate income was about 61–92% higher across the observed ranges. Median wall
time increased 3.20%, from 75.70 to 78.12 seconds; median peak memory increased
17.31%, from 1,351.09 to 1,584.90 MiB. Both complete-model results remained
FEASIBLE. These measurements establish improved solution and bound quality under
this allowance, not a shorter time to a proved optimum.

Preparation took 23.23–24.84 seconds and final native search took 33.56–35.17
seconds, within the same solver allowance. All 62 groups returned candidates in
both repeats: 17 OPTIMAL and 45 FEASIBLE in the first, 13 OPTIMAL and 49 FEASIBLE
in the second. Each assembled seed passed the complete model before use. The
expanded reference retained 160,011 variables and 462,355 constraints; the final
native model had 34,110 variables and 31,995 constraints after strengthening.

Two repeats do not establish reliable tail latency or predict other machines,
factions or scenarios. In particular, the remaining gap does not establish that
the current layout is suboptimal, and there is no estimated time to completion.

Three additional checks are recorded separately from the repeated full-world
comparison. Thracia alone retained the same proved optimum, 24,140.375 income,
and took 1.67 seconds in the final wheel versus 1.93 seconds in the baseline.
An intermediate build took 8.44 seconds on that case, prompting restoration of
the original native formulation for fewer than four provinces. These are one-off
checks, not evidence of a general small-case speedup.

A four-province holding of Thracia, Macedonia, Italia and Aegyptus used an
intermediate candidate whose formulation for four or more provinces is unchanged
in the final wheel. The baseline returned income 97,795.00 and a 20.436% gap in
61.56 seconds; the candidate returned 97,651.25 and a 2.929% gap in 61.88 seconds.
Both were FEASIBLE. This single comparison improved the bound but reduced income
by about 0.15%; it is not a uniformly better result.

A separate final-wheel run requested Cancel when the full-world live gap reached
6% or less. It returned a validated FEASIBLE layout after 46.06 seconds, retaining
income 1,558,460.0525, upper bound 1,640,076.7075 and a 4.976% gap. This confirms
graceful cancellation with the preparatory seed in a real run, not a guaranteed
time to that gap or to optimality.

## Exposing the actual connections

For at least four provinces, the factored income formulation groups wealth by its
province as well as its tax and corruption factors. Provinces with identical
factors therefore do not share one artificial wealth variable. Additional income contributions enter the
objective directly instead of passing through a single aggregate variable.
These changes preserve the objective while removing connections caused only by
how its sum was represented.

The preparatory partition starts from the original expanded reference model.
Building ownership comes from the region-to-province mapping; ownership of
product auxiliaries and economic indicators is derived recursively from their
inputs. Fixed decisions do not create connections between otherwise separate
groups.

Only ordinary reference constraint rows whose inputs are known to span multiple
provinces are eligible for temporary relaxation. Rows mentioning economic
indicators remain, as do the definitions of income factors and products. Unknown
ownership retains the row conservatively. Unsupported metadata or native
constraints skip preparation rather than guessing a partition.

The graph of all retained native constraints determines the connected groups.
It includes variables used in enforcement literals and integer products, not
just ordinary linear rows. Shared economic effects can therefore keep several
provinces together. Fixed-only constraints also remain represented, including
contradictory constant constraints.

Relaxed cross-province rows also supply necessary local constraints. Contributions
from outside a group are replaced with their most optimistic integer-domain
extremes. For a row `L <= local + external + C <= H`, where `C` is fixed and
the external contribution lies between `m` and `M`, the group must satisfy:

```text
L - C - M <= local <= H - C - m
```

This projection preserves constraints on local penalties without forcing groups
to agree on external choices during bound preparation. The extremes can be
optimistic or mutually incompatible, so passing projected rows does not establish
that a combined holding is feasible. The complete original rows are still checked
before accepting a seed and remain enforced in final search.

## Why the bounds are valid

Removing constraints enlarges the feasible set, so its maximum income is an
upper bound on the original maximum. After the temporary removals, write the
objective in native integer units as `c + sum(f_i(x_i))`, where `c` includes all
fixed contributions and the objective offset. Each connected group supplies a
safe upper bound `U_i` on `f_i` under its retained constraints:

```text
original maximum income <= relaxed maximum income <= c + sum(U_i)
```

Short CP-SAT searches can tighten the bounds obtained from each variable's
integer domain. An unfinished group keeps its certified bound; its best layout's
income never substitutes for an upper bound. Native bounds stay in integer units
while being combined and rounded outward. The exact rational income unit is
applied only when reporting income to callers.

Improved group inequalities are added to the complete original native model.
Every original constraint, including temporarily relaxed rows, remains enforced
in the final search. Attila uses this constraint relaxation without Rome II's
shared-food pricing or HiGHS LP prepass: Attila's food requirements are provincial.

## Candidates, proofs and cancellation

Local candidates become a combined seed only if their complete assignment
satisfies every original native domain and constraint. Cross-province rows are
included in this check. Independent group optima need not combine into a feasible
holding, and even a feasible combination does not automatically establish an
OPTIMAL status.

After final search, the solver restores all expanded reference decisions and
product auxiliaries, checks the original matrix and reconciles its income with
the compact objective. The owning engine also validates the resulting layout.
A validated seed survives a worse native candidate, UNKNOWN, or cancellation
before native search produces a candidate. It is reported as FEASIBLE with its
remaining bound. Contradictions between a native proof and a validated seed are
errors, not reasons to silently replace a proof status. Without a candidate or
proof, an unfinished run remains UNKNOWN; the native response's default zero is
not treated as an income bound.

The TUI shows preparation progress through the connected groups, followed by
search of the complete model. Cancel requests a graceful stop and preserves a
validated candidate when available; Force stop can discard the active candidate.
Neither the number of groups nor the remaining gap predicts how long a proof
will take. A small gap can occur even when the current layout is already optimal.

## Allowances and scope

Preparation is automatic for eligible factored-income CP-SAT models with at least
four selected provinces and four connected groups. Smaller holdings retain the
original native income grouping and extra-income aggregation, with no bound
preparation. Preparation is skipped when less than 45 seconds of a configured
overall allowance remain.
Its configured allowance is capped at 40 seconds and, for limited runs, two-thirds
of the remaining overall allowance. Each component search receives the smaller
of one second and the remaining allowance divided by the remaining waves of
component searches. This distributes the budget across groups instead of letting
early groups consume it all. Conversion and validation add overhead; these are
solver allowances, not hard wall deadlines. An unlimited full solve remains
unlimited after preparation.

Independent component searches run concurrently with one native worker each.
The number of concurrent searches is capped by the same machine-derived CPU
allocation used for the complete search. For example, four allocated workers
allow up to four single-worker components at once; final joint search still uses
four workers. This does not allocate a worker for every province or multiply the
machine allocation by the number of groups.

Simpler quadratic objectives, including the usual WRE and barbarian comparison
models, retain the expanded Boolean formulation. This stage does not change
HiGHS or Shogun 2. Cross-province economic factors, unknown ownership and retained
indicator rows may leave large groups and limit the benefit. A library of
reusable province templates or a column-generation solver is outside this change.

## Why the initial approach changed

The first sequential preparation regressed: 78.53 seconds wall time, income
546,134.78 and a 77.310% gap. It searched only 33 of 62 groups before exhausting
its allowance and produced no complete seed. A later sequential attempt also
regressed and produced no seed. Those rejected measurements remain in the raw
report; they are not included in the final-candidate ranges above.

Diagnostics on Aegyptus, Thracia and Italia motivated the revised CPU allocation.
Each compact component reached OPTIMAL with one worker in 0.40–0.60 seconds.
With four workers, all three remained FEASIBLE at a one-second allowance and
needed 1.06–2.89 seconds to prove optimality when given a longer allowance. These
were single samples of relaxed local models before row projection, not full
joint-holding measurements or a general claim that one worker is faster.

The same diagnostic exposed overly permissive public-order relaxations. Across
those three groups, local integer-domain minima ranged from -299 to -220, while
other provinces could contribute at most 61 and fixed effects contributed 11.
With a required minimum of -10, every feasible holding therefore needs a local
contribution of at least -82. Projecting that necessary condition restores a
useful restriction that was lost when the cross-province row was simply removed.

## Reproduction

Build each revision with `uv build`, export its locked production dependencies
with `uv export --frozen --no-dev --no-emit-project --format requirements-txt`,
and install the wheel in a separate environment outside the checkout using those
dependency constraints. Copy `tools/holding_benchmark.py`,
`tools/holding_benchmark_sensitivity.py` and the matching `uv.lock` alongside it.
Use the recorded driver versions and compare package hashes with the raw report.
Both variants use the same driver instrumentation to record `joint_bound_search`;
that field does not alter solver invocation.

From each isolated directory, run serially for two repeats, changing the revision
label and output directory:

```sh
env/bin/python -m tools.holding_benchmark_sensitivity \
  --game attila --algorithm cp-sat --mode joint \
  --seconds-per-case 60 --wall-seconds 150 --memory-mib 4096 \
  --revision REVISION --output-directory diagnostics/repeat-1
```

Keep every repeat outcome and its status. The driver's warning about comparison
with older benchmark matrices does not invalidate this matched comparison: both
variants here use identical scenario and guard settings. The local diagnostics
use relaxed group models and are separate from the full-holding measurements.
