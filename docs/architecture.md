# Engine architecture

The CLI and terminal UI share the same engine adapters and serialized report
schema. The domain code can also run directly without launching either interface.

## Ownership and model compilation

`games.tw.attila.model.load_attila` returns a parser with its own `GameContext`.
The context owns the selected game, building catalog, naming settings and local
identifier counters. Parsing one faction never selects it globally.

`compile_scenario(provinces, SnapshotOptions(...))` copies the mutable province
and region decision containers and creates a fresh context and solver. It shares
catalog records for reading, not decision variables. The returned `ModelSnapshot`
retains the compiled binary model and independent evaluator. Input regions remain
untouched on both success and failure, and the same catalog supports concurrent
compilation of different scenarios.

```python
from games.tw.attila.model import SnapshotOptions, compile_scenario, load_attila
from games.tw.comparison import ComparisonOptions, compare_model
from games.tw.models.model_attila import AttilaFactions, AttilaReligion

parser = load_attila(
    AttilaFactions.ATT_FACT_EASTERN_ROMAN_EMPIRE,
    AttilaReligion.CHRIST_ORTHODOX,
)
province = next(p for p in parser.provinces.values() if p.print_name == "Thracia")
compiled = compile_scenario([province], SnapshotOptions(fertility=5))
report = compare_model(compiled.model, ComparisonOptions(workers=1), compiled.economy)
```

`Problem(context=...)` is the lower-level mutable model builder. Adding provinces
to it transfers their decision ownership to that problem. Use `compile_scenario`
when retaining or reusing caller-owned provinces. Treat loaded catalog entries as
read-only; changes to imported game data belong in the importer workflow.

The old `Games` API and positional `benchmark.snapshot` / `benchmark.compare`
functions remain compatibility interfaces. Code that constructs entities without
an explicit context still reads legacy settings. New CLI/TUI compilation never
uses or writes that state. New code should pass contexts and named options.

## Application boundaries

- `twoptimizer.models` defines frozen request, building-selection, engine-result
  solver-summary and case-result dataclasses. Frozen containers do not imply deep immutability
  of native engine reports; those remain owned by their case.
- `twoptimizer.engines` translates each game's existing output into `EngineResult`.
  Native dictionaries stay at this adapter boundary so engine-specific details
  and the existing exported format remain available.
- `twoptimizer.service` validates requests, expands batches and coordinates one
  typed `CaseResult` through `solve_case_model`.
- `CaseResult.to_dict` and the compatibility `solve_case` function serialize the
  existing worker/report schema. `twoptimizer.export` writes JSON and CSV.
- `twoptimizer.progress` tracks phase timings and defines the worker progress
  protocol. `twoptimizer.runner` owns subprocess cancellation and reaping.

Solver mathematics, search parameters, proof semantics and default time limits
are unchanged by this refactor.

## Regression evidence

`tests/fixtures/attila-models.json` records model signatures generated from commit
`8a5f157` before this refactor. Six scenarios cover ERE, WRE and Aksum, Orthodox
and Catholic religions, fertility 0/1/5, researched/unresearched states, and joint
provinces. The signatures cover variable names, objective coefficients, sparse
constraint coefficients, bounds and objective offset.

`tests/test_architecture.py` checks those signatures, concurrent and interleaved
compilation, cleanup after failure, typed serialization, and independent layout
validation. Existing fixture, CLI, worker, TUI and export tests remain in place.

## Repeatable performance checks

Run uninstrumented measurements serially on an idle machine, with the same Python,
lock file, worker count and scenario on both revisions:

```sh
uv run --locked python tools/benchmark.py --game attila --repeat 3 --workers 1 \
  --output benchmark-results/architecture-attila.json
```

The helper uses the UI's default faction/province/research, CP-SAT, and no time
limit. It records interpreter/platform, request, all samples, phase timings and a
result fingerprint, and rejects repeated runs that produce different results.
Use `--game rome2` or `--game shogun2` for the other adapters.

A local Python 3.14.9 comparison against `8a5f157` used three serial ERE/Thracia
runs per revision, full research, fertility 5 and one worker. All six runs proved
income **24140.375** with identical selected buildings and metrics. Median wall
time was **6.03 s before / 5.80 s after**; ranges were **5.69–6.16 s / 5.71–6.23 s**.
These overlapping ranges show no observed slowdown on that workload; they do not
establish a general speedup or predict timings on another machine. Automatic CPU
selection remains the application default; the benchmark pins one worker for a
repeatable comparison.
