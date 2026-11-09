# Game ownership and shared optimization refactor

The refactor preserves the exact compiled models checked here while removing
obsolete execution paths and consolidating solver mechanisms. HoI4, raw game
references and existing reports remain in the repository. No game economics or
scenario assumptions were intentionally changed.

## What changed

- `games/optimization` owns backends, cancellation, progress, resource selection,
  exact conversion, budgets, conservative certificates and component utilities.
  Import-boundary tests prevent dependencies on a game's rules or the app.
- Attila owns its concrete loader, domain entities, placement and construction.
  The old generic engine, historical effect interpretation, solver wrappers and
  unused Rome parser are removed. Its CLI/report facades also live under Attila.
- A typed application registry owns commands, choices, capabilities, source
  manifests, solve-adapter selection and cache lifecycle. CLI aliases and report
  shapes remain supported; game-specific settings remain explicit.
- Three Kingdoms uses validated immutable economic records. Shogun parses building
  facts, prerequisites and uniqueness once per catalog. Raw source records retain
  provenance; these changes do not claim every imported field is now a dataclass.
- HoI4 retains its current pipeline, inspector, CLI and hourly planning modules.
  The disconnected prototype and its tests are retired. HoI4 still has no complete
  gameplay optimizer; registry capabilities reflect that state.
- Tests are organized by app, optimization, tools and game. Investigation documents
  are separate from user docs. IDE files and the requirements compatibility shim
  are removed. Original report and raw-data bytes are preserved.

Native and linear formulations remain available where solver behavior justifies
them. Games still own economic equations, which links may be relaxed, preparation
policies and independent layout evaluation. Component helpers do not make a
food relaxation valid automatically for every game.

## Correctness evidence

The baseline is `5cb4068824962e2cc2c8d03ef248b6106174b726`. Both distributions use
Python 3.14.9 and identical locked production dependencies. Measurements use
installed wheels and fresh isolated workers outside the checkout. Wheel hashes,
source manifests, model identities and all outcomes are retained in
[the report](../../reports/architecture-refactor.json).

All eight workload model identities match across revisions. Attila identities
were independently recompiled from each wheel; Rome II, Shogun 2 and Three
Kingdoms expose identities in each result. Separately, all six recorded Attila
model signatures retain identical objective coefficients, constraints, variable
counts and bounds, including a joint holding and ERE, WRE and Axum cases.

All 48 timed cases returned independently validated layouts. Each of the seven
workloads that proved an optimum retained the same income in all three samples:

| Game and workload | Proved income |
| --- | ---: |
| Attila, Thracia | 24,140.375 |
| Attila, Thracia + Macedonia | 50,563.8125 |
| Rome II, Italia | 9,733.8 |
| Shogun 2, Owari | 4,318.16 |
| Shogun 2, Owari + Mikawa | 5,497.49 |
| Three Kingdoms, Yingchuan | 627.75 |
| Three Kingdoms, Yingchuan + Changan | 1,628 |

Rome II's Italia + Magna Graecia pair remains **FEASIBLE** after the 20-second
allowance in both revisions. Its incumbent and upper bound vary between runs;
these are unfinished searches, not an optimality claim. Tied building selections
are recorded but do not define semantic equivalence.

## Timing and memory

Each workload uses one worker and seeds 0, 1 and 2. Every case receives a
20-second solver allowance, a separate 90-second process guard and a 4 GiB RSS
guard. Wall time includes imports, model preparation, search and independent
validation. Baseline runs precede candidate runs; revision order was not
randomized. A preliminary 24-case candidate validation series is also preserved,
but excluded from timing comparisons because verification hooks overlapped its
start. The final candidate series had no competing tests, builds or hooks.

| Workload | Baseline median (range), seconds | Refactor median (range), seconds |
| --- | ---: | ---: |
| Attila single | 2.063 (1.518–2.240) | 1.965 (1.871–2.077) |
| Attila pair | 16.224 (12.214–17.975) | 17.750 (14.437–18.231) |
| Rome II single | 5.963 (4.127–8.314) | 6.753 (4.126–10.836) |
| Rome II pair | 20.797 (20.754–20.913) | 20.832 (20.813–20.932) |
| Shogun 2 single | 0.606 (0.606–0.607) | 0.709 (0.608–0.910) |
| Shogun 2 pair | 0.658 (0.626–0.814) | 0.707 (0.606–0.861) |
| Three Kingdoms single | 0.859 (0.808–1.009) | 0.962 (0.959–1.010) |
| Three Kingdoms pair | 1.259 (1.110–1.326) | 1.312 (1.262–1.362) |

Several medians are slower: about 0.10 seconds for the small Shogun and Three
Kingdoms cases, 0.79 seconds for Rome single and 1.53 seconds for Attila pair.
Three samples and varying seeds cannot isolate a systematic implementation cost
from host and search variability. These results do not establish a speedup.
Peak worker RSS stayed around 112–159 MiB; the largest observed increase was
about 2.6 MiB for the Three Kingdoms pair. Full-world runtime was not measured in
this architecture pass and remains governed by the existing formulations and
search policies.

To reproduce the timed workloads, install baseline and candidate wheels into
separate environments with the same exported production lock, copy
`tools/native_product_benchmark.py` outside the checkout, and run this command
serially for each installed interpreter:

```sh
/path/to/installed/bin/python /tmp/native_product_benchmark.py \
  --variants default --default-python /path/to/installed/bin/python \
  --scope single --scope pair --repeat 3 --workers 1 \
  --single-seconds 20 --joint-seconds 20 --wall-seconds 90 \
  --output /tmp/architecture-comparison.json
```

Use distinct output paths for each revision. The driver rejects existing output
paths and retains failures. The source manifest format now uses canonical
package-relative paths. Source digests intentionally change and invalidate cached
proof reuse; historical reports remain readable and are not rewritten.
