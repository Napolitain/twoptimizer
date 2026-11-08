# Rome II joint bounds

Joint Rome II CP-SAT now prepares bounds from smaller connected groups before
searching the complete realm. The goal is to find better feasible layouts and
tighter upper bounds within the same solver allowance. The model still maximizes
income with shared food, provincial order, adjacency, worldwide bonuses and
optional building requirements enforced.

## Measured workload

The workload is Rome with all 57 named provinces together, research bonuses
disabled, world bonuses and automatic map borders enabled, CP-SAT, and no optional
building or religious constraints. Automatic worker selection gives four workers
on the measured machine.

Baseline and candidate are production wheels installed outside the checkout with
the same locked dependencies: Python 3.14.9 and OR-Tools 9.15.6755. Each sample
starts a fresh worker; startup is included. Runs are serial, without simultaneous
solver tests or profiling. The configured solver allowance is 60 seconds for the
whole case, with a 120-second wall guard and a 4 GiB worker-memory guard. Model
preparation and validation can make wall time longer than the solver allowance.
Each variant has two repeats with the same request, environment and guard limits.
No warmup sample is excluded.

The [raw report](../reports/rome-joint-bounds.json) records requests, individual
timings, statuses, income, bounds, peak worker memory, environment, source hashes
and the reproduction driver. Baseline is commit
`44a554cd805ebd32ad7f4fb6510f87746213baef`; the report identifies the measured
candidate by package source hashes.

Ranges below cover both runs of each variant. The gap is
`100 * (upper bound - income) / max(1, abs(upper bound))`.

| Metric | Baseline, two runs | Candidate, two runs |
| --- | ---: | ---: |
| Total wall time | 62.96–63.11 s | 62.69–63.16 s |
| Validated income per turn | 526,175.265–536,567.845 | 655,589.000–656,158.250 |
| Certified upper bound | 683,470.205–790,800.923 | 664,550.205–665,541.965 |
| Remaining gap | 23.014–32.149% | 1.263–1.495% |
| Peak worker RSS | 771.63–869.29 MiB | 969.98–1,030.31 MiB |
| Terminal status | FEASIBLE | FEASIBLE |

Candidate income was about 22–25% higher, and the remaining gap fell to about
1.26–1.50%, within similar total wall time. Median peak worker memory increased
about 22%, from 820.46 MiB to 1,000.15 MiB. Both full-model results remained
FEASIBLE; neither run proved optimality.

The candidates spent 23.19–23.26 seconds preparing bounds, 3.97–4.34 seconds in
model conversion and 32.53–32.82 seconds in final native search. Preparation uses
part of the same allowance. One candidate run proved all 57 local group optima;
the other proved 55 and retained valid bounds for two FEASIBLE groups. Even
proving every local optimum does not by itself prove the complete realm optimal.

These observations show solution quality and bound quality under a fixed
allowance, not time to a proved optimum. A small unresolved gap does not prove
the current layout is suboptimal. Two repeats cannot establish reliable tail
latency, and timings do not predict whether another run will finish in minutes
or hours.

Two additional checks used the same installed wheels and are included in the raw
report. A four-province realm (Italia, Magna Graecia, Cisalpina, and Corsica et
Sardinia) improved from 30,801.20 income with an 11.58% gap to 31,062.40 with a
9.77% gap, in 60.85 and 60.71 seconds respectively. This was one sample per
variant, both FEASIBLE; bound preparation took 4.06 seconds in the candidate.

A separate full-world candidate run requested Cancel when its live gap first
fell to 2% or less. It returned a validated FEASIBLE layout after 32.51 seconds,
with income 654,819.33 and a 1.586% gap. The driver checked that the result had
buildings and nonnegative shared food. This verifies graceful cancellation with
the new preparatory seed in a real run; it is not a guaranteed time to 2%.

## Why the bounds are valid

The solver first identifies the explicitly tagged global-food lower-bound row
in the linear joint model. Only that row is relaxed for the preparatory bound
calculation. Fixed-variable substitution and propagation simplify the remaining
integer model, whose constraint graph determines the connected groups. Every
other row remains: a shared requirement or bonus can keep several provinces in
one group. This does not assume provinces are independent because they have
similar names, slots or building templates.

Write the full objective as `c + sum(f_i(x_i))`, where `c` contains fixed income
contributions. Write the shared food requirement as
`F0 + sum(F_i(x_i)) >= R`, where `F0` contains fixed food contributions. For any
nonnegative integer price `lambda`, a feasible realm satisfies:

```text
income <= income + lambda * (food - R)
       <= c + lambda * (F0 - R) + sum(U_i)
```

Here, `U_i` is a safe upper bound for `f_i(x_i) + lambda * F_i(x_i)` subject to
all retained constraints in group `i`. The proof uses a nonnegative price and the
original food lower bound. Fixed income, fixed food and the required amount all
matter; dropping any of them can invalidate the result.

HiGHS solves a continuous relaxation to suggest a useful integer price. This is
a heuristic choice of multiplier, not an exact LP certificate. If pricing does
not provide a usable nonnegative integer, zero is a valid fallback. The group
bounds come from CP-SAT search or safe integer-domain bounds. Unsolved groups
keep their safe bounds; their incumbents are never substituted for upper bounds.
Unsafe integer scaling skips the preparatory approach.

Each group inequality is added to the original joint model as a valid bound.
The final CP-SAT search still enforces the global-food constraint and all other
original constraints. There is no relaxation of the requested final layout.

## Candidates, proofs and cancellation

Local candidates can be combined into a search hint only when the complete
assignment passes every domain and row of the original joint matrix, including
shared food. The owning Rome optimizer independently evaluates the final layout's
economics as well. A stronger valid seed is retained if native search returns a
worse candidate, returns UNKNOWN, or is cancelled before producing one.

Such a retained layout remains FEASIBLE until a terminal proof establishes more.
Partial component searches do not create an OPTIMAL status. Native proof statuses
are preserved; a contradiction between a native proof and a validated seed is an
error. Reports retain the native status when it differs from the final reported
status. An absent candidate remains absent rather than becoming zero income.

The TUI reports the preparatory phase, including food pricing and progress through
connected groups, before the complete-model search. Live income and bounds remain
observations, not a completion countdown. Cancel requests a graceful stop; a
returned candidate is independently checked before it is retained. Force stop can
discard the active candidate.

## Allowances and scope

The stage is automatic for eligible joint Rome II CP-SAT models. It is skipped
when fewer than four connected groups remain or when less than 45 seconds of
the configured overall allowance remain. Its preparatory allowance is capped at
40 seconds and at two-thirds of the remaining allowance for limited runs. An
unlimited full solve stays unlimited after this bounded preparation.

The LP price estimate receives at most ten configured seconds; each group search
receives at most one configured second, all within the shared preparation
allowance. Conversion and validation add overhead, so these are not strict
wall-clock guarantees. The pinned OR-Tools HiGHS backend cannot interrupt an
active native LP price estimate. Cancel may wait for that stage to return;
Force stop remains available.

Worker selection stays machine-based. Groups run in sequence using the same
worker allocation as the full solver. These measurements use four workers;
additional-core scaling is unmeasured and must not be inferred from them.

The food-price stage is specific to Rome II. Attila's food constraints are
provincial, and ERE's factionwide order links require a different decomposition;
the [Attila method](attila-joint-bounds.md) documents that separate implementation.
No Attila or Shogun 2 performance gain is established by this Rome experiment.
Building a complete template library or a column-generation solver is also
outside this change.

## Reproduction

Build each revision with `uv build`, export its locked production dependencies
with `uv export --frozen --no-dev --no-emit-project --format requirements-txt`,
and install its wheel into a separate environment outside the checkout using
those exact dependency constraints. Copy `tools/holding_benchmark.py`,
`tools/holding_benchmark_sensitivity.py` and the matching `uv.lock` alongside each
environment. The report embeds both recorded benchmark drivers. The candidate
driver adds only a `joint_bound_search` report field for preparatory details;
solver invocation, allowances and the sensitivity driver are unchanged.

From each isolated directory, run serially for each of two repeats, changing the
revision label and output directory:

```sh
env/bin/python -m tools.holding_benchmark_sensitivity \
  --game rome2 --algorithm cp-sat --mode joint \
  --seconds-per-case 60 --wall-seconds 120 --memory-mib 4096 \
  --revision REVISION --output-directory diagnostics/repeat-1
```

Compare the installed package and driver hashes with the raw report, and retain
all repeat outcomes, including FEASIBLE or interrupted runs. The driver's warning
about comparison with older benchmark matrices does not preclude this matched
before/after comparison; both variants here use the same configured limits.

For the additional checks, extract the embedded `rome-bound-checks.py` driver
alongside the copied `tools` directory and run it with `--case four` or
`--case gap`, plus `--output OUTPUT.json --revision REVISION`.
