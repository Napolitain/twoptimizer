# Engine architecture

The CLI and terminal UI share the same engine adapters and serialized report
schema. The domain code can also run directly without launching either interface.

## Ownership and model compilation

`games.tw.attila.model.load_attila` returns a parser with its own `GameContext`.
The context owns the selected game, building catalog, naming settings and local
identifier counters. Parsing one faction never selects it globally.

`compile_scenario(provinces, SnapshotOptions(...))` copies the mutable province
and region decision containers and creates a fresh context and solver. It shares
recursively frozen catalog records, not decision variables. The returned `ModelSnapshot`
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
when retaining or reusing caller-owned provinces. Loaded catalogs enforce read-only ownership at runtime. Use `thaw` to create
caller-owned inputs; changes to imported game data belong in the importer workflow.

Entities, parsers and `Problem` require an explicit context. `AttilaGame` and
`Rome2Game` can create a fresh context when constructing a game; that context is
owned by the game and never published globally. Identifiers are allocated within
the owning context, including synthetic models in tests.

The former `Games`, global identifier counters, `benchmark.snapshot` and
`benchmark.compare` APIs have been removed. Call `compile_scenario` with
`SnapshotOptions`, and `compare_model` with `ComparisonOptions`. Import
`RunConfig` from `twoptimizer.models` and `export_session` from
`twoptimizer.export`. The duplicate `games.tw.attila.main` demonstration was
removed; use `uv run --locked twoptimizer attila` for the maintained CLI.

## Application boundaries

- `twoptimizer.models` defines frozen request, building-selection, engine-result,
  solver-summary and case-result dataclasses. Frozen containers do not imply deep
  immutability of native engine reports; those remain owned by their case.
- `twoptimizer.engines` translates each game's existing output into `EngineResult`.
  Native dictionaries stay at this adapter boundary so engine-specific details
  and the existing exported format remain available.
- `twoptimizer.service` validates requests, expands batches and coordinates one
  typed `CaseResult` through `solve_case`.
- `solve_case` returns the typed result. Workers explicitly call `CaseResult.to_dict`
  at the JSON boundary, preserving the existing worker/report schema.
  `twoptimizer.export` writes JSON and CSV.
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

Removing the compatibility layer was compared separately against `74304d1` on
the same workload: three serial runs per revision had identical result
fingerprints and proved the same optimum. Median wall time was **5.70 s before /
5.50 s after**, with ranges **5.65–6.31 s / 5.40–5.85 s**. These ranges overlap;
the comparison shows no observed regression rather than a general speedup.

## Domain modules and ownership

Attila separates typed `scenario` inputs, JSON `scenario_validation`, exact
`algebra`, solver `compiler`, domain `economy` rules and `reporting`. Campaign,
province, region, metric, project and external-effect inputs are frozen records.
The engine uses their named fields; JSON dictionaries enter through validation
and leave through explicit serialization. Boolean polynomial indicators also use
named records rather than positional tuples.

Rome II separates source `catalog` and `records`, immutable `scenario` settings,
`placement` policy, constraint `compiler`, native `backends` and solver
`optimization`. Per-build `EffectTerms` owns the mutable expression buckets.
Report creation and independent replay share `provenance.model_fingerprint` so
changes in extracted mathematics remain part of source verification. Shogun 2
has corresponding catalog, scenario and report/source record modules.

`games.tw.immutable` freezes mappings recursively behind a mapping proxy and
turns JSON arrays into tuples. File catalogs are cached by path, nanosecond
modification time and size. Cache hits safely share immutable data; changed file
revisions load new data. `thaw` produces independent JSON containers when a
caller needs to customize an input or export a report.

Parsed building builders are converted to frozen `BuildingTemplate` records.
Templates hold immutable effects and metadata and contain no solver variables.
Each model instantiates separate mutable decision buildings. Template metadata
can be shared; decision effect dictionaries and variables belong to one model.

The terminal app separates workspace composition/style, modal screens,
presentation formatting and application event handling. The wheel bundles
`workspace.tcss` alongside the Python modules.

Shared test factories live under `tests/support`; fixtures are registered in
`tests/conftest.py`. Test modules do not import other test modules. Ownership
regressions cover caller mutation, nested catalog writes, exports, cache refresh,
model isolation, repeated solver builds and constant native constraints, alongside
the existing independent economic calculations and model signatures.
