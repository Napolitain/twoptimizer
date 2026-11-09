# Holding performance baseline

Measured on 2026-11-08 against installed-wheel commit
`6e03a72f0f56a9f26266fa875f0e265143eea5a7`. This is a baseline for the existing
models, before the optional constraint comparison and special-building audit changes.
This is a **historical benchmark**: current releases support only CP-SAT and
HiGHS. The CBC, SCIP and portfolio observations below retain their original
meaning; no HiGHS performance was measured in this baseline.

All 65 Shogun provinces solved independently to optimality in 1.84–1.90 seconds.
Joint ownership was substantially harder: one run proved optimal in 8.05 seconds;
the other returned a feasible solution after 13.01 seconds, with a 0.91% gap.
Attila's full holding spent about 38 seconds building/converting its model before
meaningful search. Rome's full joint holding also remained unproved. These results
do not support a universal fastest backend or a predictable completion time.

## Method

The 59 samples ran serially through the real application worker, without profiling,
coverage, or cached proofs. Each sample started a fresh worker; independent cases
reused that worker's imports. Wall time includes startup, preparation, conversion,
search, result validation, and shutdown. Filesystem caches may be warm on later
runs. Main comparisons have two repeats; diagnostics have one. No wall or memory
guard fired, and every requested case returned a solver status.

The machine was an Intel Xeon Platinum 8573C, Linux 6.18.57, with a four-CPU cgroup
quota and 16 GiB memory limit. Automatic worker selection chose four for CP-SAT
and SCIP and one for CBC. Native SCIP multithreading depends on its bundled build;
this records the application setting, not measured CPU utilization. Dependencies:
Python 3.14.9, OR-Tools 9.15.6755 (CP-SAT, CBC 2.10.12, SCIP 10.0.0/SoPlex 8.0.0),
PySCIPOpt 6.3.0 (SCIP 10.0.2), NumPy 2.5.4, Textual 6.12.0.

Defaults were ERE/all technology/Orthodox/fertility 5 for Attila; Rome/no research
bonuses for Rome II; and Oda/all arts/native soil/town wealth 0/tax 30 for Shogun.
World bonuses were enabled, bundled adjacency was used, and no optional constraints
or comparison solves were requested. Pairs were Thracia/Macedonia,
Italia/Magna Graecia, and Owari/Mikawa respectively.

A **configured solver allowance** is not guaranteed native search time: some
backends include conversion in that allowance. The primary matrix divides the same
total allowance among independent cases; the joint request gets it once. Separate
wall guards cover the whole batch (90 seconds for pairs, 120 for all provinces).
A 2,048 MiB worker RSS guard samples Linux `VmHWM` every 50 ms and at shutdown;
it may overshoot between samples and excludes the parent process. Timings and
memory measure this container, not the user's computer.

`O` means optimal, `F` feasible but unproved, and `U` unknown with no incumbent.
A complete sample can contain `U`. Missing income/bounds remain null. Gaps use
`100 × (upper bound − income) / max(1, |upper bound|)` after summing complete
independent cases. Independent totals describe separate hypothetical realms;
they are not jointly legal ownership layouts and must not be compared with joint
income as though the difference were solver quality.

## All provinces, CP-SAT

Each sample had a **12-second total configured allowance**: about 0.19 seconds
per Attila province, 0.21 for Rome, and 0.18 for Shogun when independent. The
build/conversion and native-search columns are medians; RSS is the largest repeat.
Different statuses separated by semicolons refer to the two repeats.

| Game / mode | Provinces | Wall range (s) | Build + conversion (s) | Native search (s) | Peak RSS (MiB) | Statuses | Gap range (%) |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| Attila / independent | 62 | 26.41–27.14 | 14.20 | 8.72 | 220.4 | 61F+1U | — |
| Attila / joint | 62 | 39.04–39.19 | 38.41 | 0.07 | 880.2 | 1U | — |
| Rome II / independent | 57 | 14.16–14.31 | 3.50 | 8.94 | 181.1 | 57F; 1O+56F | 50.37–50.80 |
| Rome II / joint | 57 | 13.37–13.48 | 9.95 | 2.33 | 301.6 | 1U | — |
| Shogun 2 / independent | 65 | 1.84–1.90 | 0.21 | 0.36 | 143.7 | 65O | 0.00 |
| Shogun 2 / joint | 65 | 8.05–13.01 | 0.14 | 9.37 | 265.9 | 1O; 1F | 0.00–0.91 |

The Attila joint request received only 0.067 seconds of native search after
38.41 seconds of build/conversion; its unknown result mainly diagnoses preparation
pressure. Rome's joint request received 2.33 seconds of native search. Neither
row measures time required to prove the full holding optimal.

Similar aggregate model counts did not imply similar difficulty. Attila had
34,053 solver variables/31,003 constraints across its independent cases versus
33,987/30,942 in one joint model. Rome had 23,220/47,101 versus 24,453/53,378;
Shogun had 3,491/5,616 versus 3,491/5,360. Counts sum the largest reported
formulation per case and stage; reference and solver stages are not added.

## Two-province backend comparison

Each sample had a **six-second total configured allowance**: three seconds per
independent case or six for the joint case. Times are medians with observed ranges
in parentheses. Gap ranges include both repeats; status abbreviations count cases.
A bounded run that used its allowance is not a measurement of time to optimality.

| Game / backend | Independent wall (s) | Independent status / gap (%) | Joint wall (s) | Joint status / gap (%) |
| --- | ---: | --- | ---: | --- |
| Attila / cp-sat | 6.31 (5.37–7.26) | 1O+1F / 2.78–6.51 | 7.14 (7.07–7.22) | 1F / 8.81–10.30 |
| Attila / cbc | 7.25 (7.12–7.38) | 2U / — | 9.57 (9.56–9.57) | 1U / — |
| Attila / scip | 10.14 (10.08–10.19) | 2F / 53.04–57.85 | 9.60 (9.59–9.61) | 1F / 51.38 |
| Rome II / cp-sat | 6.66 (6.64–6.68) | 2F / 13.71–13.73 | 6.64 (6.63–6.65) | 1F / 15.26–15.43 |
| Rome II / cbc | 6.93 (6.78–7.08) | 2F / 9.93 | 6.83 (6.79–6.86) | 1F / 9.99 |
| Rome II / scip | 6.86 (6.79–6.93) | 1O+1F / 8.97–9.06 | 6.94 (6.94–6.95) | 1F / 12.30–13.57 |
| Rome II / portfolio | 6.69 (6.65–6.72) | 2F / 9.45–12.70 | 6.63 (6.62–6.63) | 1F / 15.69 |
| Rome II / scip-nonlinear | 6.63 (6.63–6.64) | 2F / 18.06 | 6.61 (6.60–6.61) | 1F / 21.01–24.42 |
| Shogun 2 / cp-sat | 0.57 (0.52–0.61) | 2O / 0.00 | 0.55 (0.53–0.58) | 1O / 0.00 |
| Shogun 2 / cbc | 0.54 (0.54–0.55) | 2O / 0.00 | 0.54 (0.53–0.54) | 1O / 0.00 |
| Shogun 2 / scip | 0.57 (0.57–0.58) | 2O / 0.00 | 0.65 (0.64–0.66) | 1O / 0.00 |

All three backends agreed on the proven Shogun pair income in each mode:
7,621.24 for independent cases and 5,497.49 for joint ownership. Its subsecond
wall times are dominated by worker startup. Attila CP-SAT found substantially
stronger incumbents than CBC/SCIP under these short allowances; CBC found none.
Rome CBC found the best joint incumbent in these samples (20,318), but no Rome
pair backend proved the complete holding optimal. Portfolio and nonlinear SCIP
did not establish an advantage here. Gap comparisons also reflect the strength
of each backend's upper bound.

The JSON reports preserve per-case income, bound, model counts, phase timings,
and memory. Rome CBC/SCIP, portfolio, and nonlinear runs do not expose a complete
native build/search split, so their derived split is null instead of zero.

## Longer diagnostic allowances

These are single CP-SAT samples with **larger total allowances**, not fair speed
comparisons against the 12-second matrix.

| Game / mode | Configured allowance | Wall (s) | Build + conversion (s) | Native search (s) | Peak RSS (MiB) | Statuses | Gap (%) |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: |
| Attila / independent | 1 s × 62 cases | 75.17 | 14.56 | 56.80 | 228.3 | 6O+56F | 10.66 |
| Rome II / independent | 1 s × 57 cases | 51.61 | 3.53 | 46.12 | 204.1 | 12O+45F | 16.60 |
| Attila / joint | 60 s × 1 case | 86.53 | 37.63 | 39.26 | 1,610.5 | 1F | 77.64 |

The longer independent runs found incumbents for every province, but most remained
unproved. The 60-second Attila joint run found income 802,558.86 with upper bound
3,589,075.415: a 77.64% gap. Its 37.63-second build/conversion and 39.26-second
native search account for most of the 86.53-second wall time; validation and
other overhead also matter. This is evidence of both preparation cost and a
remaining difficult search, not a certified best whole-world layout.

The next performance target is Attila's joint model construction/conversion,
followed by stronger joint search formulations or incumbents for Attila and Rome.
Two repeats, one faction per game, and short allowances do not justify changing
the default backend globally. The later restriction to CP-SAT/HiGHS simplifies
maintenance; it is not a conclusion that CP-SAT wins every workload. Full-world
CBC/SCIP runs were omitted to keep this
diagnostic bounded; all three were compared on the representative pairs. These
measurements concern the current bundled model, not validation against installed
game files or an economy ranking across games.

## Artifacts and reproduction

Raw reports:

- [All Attila](../../reports/holding-performance-all-attila-cpsat.json),
  [all Rome](../../reports/holding-performance-all-rome2-cpsat.json),
  [all Shogun](../../reports/holding-performance-all-shogun2-cpsat.json).
- [Pair backends](../../reports/holding-performance-pairs.json) and
  [Rome alternatives](../../reports/holding-performance-rome-alternatives.json).
- [Longer Attila independent](../../reports/holding-performance-sensitivity-attila.json),
  [Rome independent](../../reports/holding-performance-sensitivity-rome2.json), and
  [Attila joint](../../reports/holding-performance-sensitivity-attila-joint.json).

Each report records the baseline commit, dependency-lock hash, execution harness
hash, machine configuration, full requests, and source-file hashes per sample.
After measurement, budget labels and derived timing summaries were clarified:
unknown native conversion timing stays null. `summary_revision` identifies that
summary code; numeric case observations and the original execution hash remain
unchanged.

To measure the two supported solvers against the current checkout (Linux `/proc`
required), write new reports. These commands do not reproduce the retired-backend
rows above:

```sh
uv run --frozen python -m tools.holding_benchmark --size pair \
  --algorithm cp-sat --algorithm highs --repeat 2 \
  --solver-seconds 6 --wall-seconds 90 --memory-mib 2048 \
  --output /tmp/holding-pairs.json
uv run --frozen python -m tools.holding_benchmark --size all \
  --algorithm cp-sat --repeat 2 --solver-seconds 12 --wall-seconds 120 \
  --memory-mib 2048 --output /tmp/holding-all.json
uv run --frozen python -m tools.holding_benchmark_sensitivity \
  --game attila --game rome2 --seconds-per-case 1 --wall-seconds 180 \
  --output-directory /tmp/holding-sensitivity
uv run --frozen python -m tools.holding_benchmark_sensitivity \
  --game attila --mode joint --seconds-per-case 60 --wall-seconds 120 \
  --output-directory /tmp/holding-sensitivity
```

The measured baseline used a `git archive` extraction of the stated commit,
`uv sync --locked`, `uv build`, and the resulting wheel installed with
`uv pip install --reinstall-package napolitain-twoptimizer`. The driver and
`uv.lock` were copied outside that source archive, then invoked with the archive's
Python 3.14 virtual environment and `--revision 6e03a72f0f56a9f26266fa875f0e265143eea5a7`.
Imports were verified to resolve to installed `site-packages`; concurrent native
solver tests were paused. Reproducing that baseline requires those pinned sources,
not the subsequently edited checkout. For retired backends, use the historical
driver and dependency environment (the driver is preserved in commit `6c2faed`);
the current driver rejects those solver names. The archived execution driver used
`--search-seconds`, retained as an alias for the clearer `--solver-seconds`.
