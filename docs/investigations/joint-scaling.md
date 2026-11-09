# Joint Attila and Rome II performance

Full-world joint optimization still takes substantial search. The changes in
this investigation remove redundant compilation work and expose live search
progress; they do not establish a short time to proven optimality.

## Workload and method

The cases reproduce the default CP-SAT joint requests with no optional building
or religious-influence constraints: Eastern Rome, all research and all 62 Attila
provinces; Rome, no research and all 57 Rome II provinces. Bundled borders and
world bonuses remain enabled. Both use fertility 5 where applicable.

Baseline is commit `adc69d2381c3bd53d6ded61a274f594c7345da93`. Baseline and
candidate were built as wheels and installed into separate environments outside
the checkout, with the same locked dependencies. Installed package files were
checked against their source hashes. Python was 3.14.9, OR-Tools 9.15.6755, on
an Intel Xeon Platinum 8573C host with a four-CPU cgroup allocation and 16 GiB
memory limit. Automatic worker selection chose four workers.

Each variant has two serial runs per game. Each run starts a fresh worker;
startup is included and no warmup sample is excluded. No native test, profiling
or competing benchmark workload ran alongside measurements. Each case has a
60-second configured solver allowance, a 150-second wall guard and a 4 GiB
worker RSS guard. Conversion consumes part of the solver allowance, while other
preparation and validation occur outside it. The application still defaults to
unlimited solving.

The [raw measurement record](../../reports/joint-scaling.json) contains individual
observations, requests, source hashes, limits, environment and solver statuses.
The before/after cases use matching limits. Two repeats show the observed range,
not a reliable tail-latency estimate or a general speed guarantee.

## Measurements

Ranges cover the two runs. Model preparation includes measured build and
conversion phases. Income is per turn; higher is better. Gap is
`100 * (upper bound - income) / max(1, abs(upper bound))`; lower is better.

| Game | Metric | Baseline | Candidate |
| --- | --- | ---: | ---: |
| Attila | Model preparation | 41.63–41.80 s | 14.17–14.61 s |
| Attila | Total wall time | 89.73–90.59 s | 76.93–78.73 s |
| Attila | Feasible income | 775,336–807,701 | 923,314–937,422 |
| Attila | Remaining gap | 77.50–78.40% | 59.06–59.53% |
| Rome II | Model preparation | 10.07–11.18 s | 4.42–4.92 s |
| Rome II | Total wall time | 61.69–62.06 s | 63.01–63.19 s |
| Rome II | Feasible income | 497,290–505,000 | 522,330–538,831 |
| Rome II | Remaining gap | 45.47–47.04% | 27.01–33.85% |

Median preparation fell about 66% for Attila and 56% for Rome II. Rome's total
wall time increased about 2%; this is not an end-to-end latency improvement for
that bounded case. Both candidates spent more of the allowance in native search:
Attila about 58 seconds rather than 36–37, and Rome about 55–56 rather than 49–50.
Different formulations also change search behavior, so better incumbents cannot
be attributed solely to preparation savings. Every run remained **FEASIBLE**;
none proved optimality within the allowance.

Attila peak worker RSS fell from 1,558–1,592 MiB to 1,344–1,367 MiB. Rome rose
from 761–764 MiB to 768–782 MiB. Attila native input grew slightly, from 33,987
variables / 30,942 constraints to 34,111 / 31,314, because of the exact linear
branches. Rome shrank from 24,453 / 53,378 to 22,983 / 48,965. A smaller model
is not always a stronger model.

## Removed work

- Attila repeatedly copied growing income polynomials while adding regions and
  upkeep. Exact rational terms now accumulate in one pass, retaining term order
  and cancellation behavior.
- Compact Attila compilation expanded the entire tax objective again and then
  subtracted its regional components. It now builds the non-tax remainder
  directly, including upkeep, exports and other supported income.
- Both engines repeatedly scanned unrelated building-selection groups.
  Reverse membership indices restrict checks to relevant groups.
- Rome multiplied wealth by selectors already constrained to one, creating
  redundant product variables and rows. Those products now use wealth directly;
  the mandatory decisions and canonical proof model remain intact.
- Attila tax/corruption factors that are affine in exclusive building choices
  use exact conditional linear branches. Nonlinear or clamped factors retain
  the general formulation. Signed coefficients, optional choices and existing
  simultaneous-building permissions are preserved.

An instrumented baseline Attila compilation recorded about 80 million group
intersection calls. Profiling timings were used to locate work, not as measured
production latency. The expanded reference model remains available for result
validation; independent economic evaluation and all existing constraints remain.

Engine source fingerprints change with these edits. Historical reports retain
their original provenance and are not relabeled as current results. Strict
source-based replay/resume requires a report from the matching revision;
canonical proof identity remains separate from this source fingerprint.

## Why joint search remains hard

The selected Rome data has cross-province economic bonuses on forced buildings,
so those contributions are constants. Food still couples the provinces. Solving
each province separately with its own food requirement changes the problem;
allowing every province to ignore food can produce an infeasible realm.

For Eastern Rome with all research, optional legendary governors supply
factionwide public order. Their choices affect the feasibility of layouts in
other provinces. Treating those bonuses as fixed or deleting the links would
change the problem. Model size alone does not describe the difficulty of
proving that no better combination exists.

## Templates and further exact reductions

Immutable building catalogs and some per-model calculations are already cached.
A single best layout per province is insufficient for joint optimization: a
lower-income layout can contribute food, public order or another shared benefit
that permits a better total result.

A useful next formulation would retain non-dominated local layouts, including
their resource use and outgoing effects, and let a smaller master problem choose
between them. Incoming bonuses must also be represented, since they can change
local income and feasibility. Exactness requires complete alternatives or a
procedure that proves omitted alternatives cannot improve the master result.
A heuristic library alone supplies good hints, not an optimality certificate.

Reuse keys must include available buildings, slots, resources, fertility,
modifiers, restrictions and relevant coupling behavior. Name-independent shapes
are only candidates for reuse. Disconnected components can be solved separately
only after accounting for shared food, uniqueness, factionwide effects and all
other cross-component constraints.

A source-only shape audit found 51 province shapes among Rome's 57 provinces
and 54 raw slot shapes among Attila's 62. Whole-province duplication is therefore
limited in these signatures. Region-level signatures have more repetition:
30 shapes among Rome's 173 regions and 42 among Attila's 186. These are not
equivalence certificates: Attila's raw signatures, for example, do not apply
faction/religion eligibility or incoming effects. The raw record includes the
audit method, data hashes, repeated classes and reproduction script.

For the detected Rome food coupling, an exact master could coordinate complete
income–food alternatives after fixing constant realm bonuses and party choices.
For ERE, alternatives must also describe exported factionwide order and the
incoming order each layout needs. Region templates additionally need wealth
categories, modifiers and tax/corruption behavior, not just a scalar income.

## Search visibility

The TUI now receives native model counts before CP-SAT search and displays
candidate income, upper bound, gap and elapsed search time during the solve.
Values use original income units. Events are throttled while retaining the first
candidate and final observation. A missing incumbent remains absent; UNKNOWN
does not create a zero bound from a solver default.

At the measured revision, live candidates remained separate from validated
results, and Cancel terminated the active case without saving its candidate.
The current TUI instead requests a graceful CP-SAT stop and independently
validates any returned candidate before retaining it with the bound and gap;
Force stop can still discard the active candidate. See [usage](../usage.md) for the
current cancellation behavior and HiGHS interruption limitation. The historical
measurements above are unchanged. Solver workers remain automatic, and no time
limit or relaxed optimality criterion was added by this investigation.

## Reproduction

Build each revision with `uv build`, install its wheel with the locked
dependencies in its own environment, and copy `tools/holding_benchmark.py`,
`tools/holding_benchmark_sensitivity.py` and `uv.lock` beside that environment.
From that directory, outside the repository, run the following serially for
each variant and repeat, changing the revision label and output directory:

```sh
env/bin/python -m tools.holding_benchmark_sensitivity \
  --game attila --game rome2 --mode joint \
  --seconds-per-case 60 --wall-seconds 150 --memory-mib 4096 \
  --revision REVISION --output-directory diagnostics/repeat-1
```

Use the preserved source hashes to identify the measured candidate. Do not
compare a bounded FEASIBLE result with a time-to-optimal measurement, or count
the configured 60 seconds as 60 seconds of native search.
