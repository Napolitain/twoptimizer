# CP-SAT and HiGHS performance

Measured on 2026-11-08 against installed-wheel source commit
`6e5d03aab11e1f70805c53c52e8299a534002db5`. CP-SAT is the default;
HiGHS is the supported alternative. This compares the current pair workloads,
without extending the historical CBC/SCIP measurements.

## Results

Each independent sample solves two separate provinces; a joint sample solves one
combined holding. Times and income/gaps show the range of two repeats. `O` means
optimal, `F` feasible but unproved, and `U` unknown without an incumbent. A completed
sample is not necessarily an optimal solve. Status counts separated by semicolons
refer to different repeats.

| Game / backend / mode | Wall (s) | Income | Gap (%) | Case statuses |
| --- | ---: | ---: | ---: | --- |
| Attila / cp-sat / independent | 5.09–5.20 | 50,489.88 | 0.00 | 2O |
| Attila / cp-sat / joint | 7.09 | 49,788.40–50,563.81 | 9.29–11.13 | 1F |
| Attila / highs / independent | 7.38–7.43 | 19,134.38 | 66.02 | 2F |
| Attila / highs / joint | 7.32–7.34 | 8,533.43 | 85.03 | 1F |
| Rome II / cp-sat / independent | 6.74–6.75 | 18,715.30–19,033.00 | 12.92–13.69 | 2F |
| Rome II / cp-sat / joint | 6.65–6.67 | 18,918.20–19,382.90 | 16.41–18.41 | 1F |
| Rome II / highs / independent | 7.19–7.23 | 14,500.10 | 32.53 | 2F |
| Rome II / highs / joint | 7.23–7.26 | 16,984.90 | 26.64 | 1F |
| Shogun 2 / cp-sat / independent | 0.53–0.58 | 7,621.24 | 0.00 | 2O |
| Shogun 2 / cp-sat / joint | 0.51–0.55 | 5,497.49 | 0.00 | 1O |
| Shogun 2 / highs / independent | 0.60–0.64 | 7,621.24 | 0.00 | 2O |
| Shogun 2 / highs / joint | 0.58 | 5,497.49 | 0.00 | 1O |

CP-SAT found better incomes and smaller gaps than HiGHS on the Attila and Rome
pairs under these allowances. CP-SAT proved both independent Attila provinces
optimal in both repeats; neither backend proved the Attila joint holding or the
complete Rome pair. Both backends agreed on Shogun's optimal incomes in both modes
and repeats. The Shogun runs are dominated by worker startup, so their small wall
time differences do not establish a general speed ranking.

Peak worker RSS stayed below 259 MiB. All 24 samples returned, and no wall or memory
guard fired. Native time limits can overrun slightly; for example Rome HiGHS native
calls took about 6.3 seconds in aggregate despite a six-second configured allowance.
These results support retaining CP-SAT as the default for the measured workloads;
they do not establish which backend would finish every larger model first.

Independent income sums describe separate hypothetical realms. They are not legal
joint holdings, so income differences across modes do not measure solver quality.
Gaps also depend on upper-bound strength. A missing income or bound remains null;
it is never treated as zero. Aggregate gap is
`100 × (sum of upper bounds − sum of income) / max(1, |sum of upper bounds|)`.

## Method and limits

All 24 samples ran sequentially, with no competing solver tests, coverage, or
profiling. Each sample started a fresh application worker; independent cases reused
that worker's imports. There was no cached proof or constraint comparison. Filesystem
caches could be warm. Wall time includes startup, model preparation/conversion,
search, validation, and shutdown. The raw report preserves each phase, model counts,
source-file hashes, and effective worker settings.

Both modes received **six seconds of total configured solver allowance**: three
seconds per independent case or six seconds for the joint case. Conversion can
consume this allowance; native search time is recorded separately. A separate
90-second wall watchdog and 2,048 MiB worker RSS guard covered the whole sample.
RSS uses Linux `VmHWM`, sampled every 50 ms and at shutdown, and excludes the parent;
the memory guard can overshoot between samples. These bounded runs measure solution
quality under short allowances, not the eventual time to optimum.

Pairs/settings: Attila Thracia/Macedonia with ERE, all technology, Orthodox,
fertility 5; Rome Italia/Magna Graecia with Rome and research disabled; Shogun
Owari/Mikawa with Oda, all arts, native soil, town wealth 0, tax 30. Bundled
adjacency and world bonuses were enabled; optional constraints were empty.
Only these pairs and default factions were measured, not whole-world runs.
These are the current static economic models. Attila still has
[capital/legendary availability gaps](attila-special-audit.md), so the reported
incomes are not a certification of campaign-valid construction plans.

The machine was INTEL(R) XEON(R) PLATINUM 8573C, Linux, with a four-CPU cgroup quota and
16 GiB memory limit. Automatic worker selection requested four for both backends.
This is an allocation setting, not a measurement of CPU utilization. Python was
3.14.9, OR-Tools 9.15.6755, NumPy 2.5.4, and Textual
6.12.0. HiGHS 1.12.0 ran through OR-Tools MathOpt using its
bundled library; the shared adapter resets its thread scheduler between solves.

## Artifact and reproduction

[Raw measurements](../../reports/holding-performance-cpsat-highs.json) record the
exact source commit, lock hash, harness hash, machine configuration, requests,
observations, and summaries. The production wheel was installed in a separate
Python 3.14 environment. All 223 package source/data/style files checked matched
the committed checkout before the run. The driver and lock were copied outside
the checkout, and imports resolved to the installed wheel.

Run against the current checkout with:

```sh
uv run --frozen python -m tools.holding_benchmark --size pair \
  --algorithm cp-sat --algorithm highs --repeat 2 --solver-seconds 6 \
  --wall-seconds 90 --memory-mib 2048 \
  --output /tmp/holding-performance-cpsat-highs.json
```

To reproduce the pinned measurement, build the stated commit with `uv build`,
install the wheel in an isolated environment, copy `tools/holding_benchmark.py`
and `uv.lock` into a separate run directory, and run the same module using that
environment's Python with
`--revision 6e5d03aab11e1f70805c53c52e8299a534002db5`. Linux `/proc` is required
for the memory guard. Do not run other solver workloads concurrently.
