# Application and engine architecture

The CLI and terminal UI share request validation, scenario preparation and typed
application results. Their existing JSON and CSV report formats are preserved by
serializers at the output boundary. The domain code can also run directly without
launching either interface.

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

Each Attila `Economy` resolves source effects once and indexes their region and
province recipients. Building-only modifiers retain their producer check; province
effects are counted once per province even when multiple regions receive them.
The index has the same fixed-source lifetime as the compiled expression caches.
Recompiling after changing caller-owned inputs creates a fresh index. No effect
cache is shared globally or across models.

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

Total War cases in both interfaces optimize **income only**. Attila's `--objective income` remains
accepted; wealth, legacy and campaign objective weights are rejected by the
application. Lower-level domain APIs retain their existing modes for engine
regressions and direct use.

The call paths are:

```text
CLI parser -> RunRequest -> make_jobs -> solve_case -> game adapter -> engine
                                        |                             |
                                        +-- CaseResult <- EngineResult+
                                            |
                                            +-> CLI report serializer

TUI widgets -> RunConfig -> make_jobs -> CaseRunner -> worker subprocess
                                                       |
                                                       +-> RunConfig.from_dict
                                                       +-> solve_case
                                                       +-> CaseResult.to_dict
```

`twoptimizer.models` defines `RunConfig` for settings and province selection,
and `RunRequest` for additional batch axes: factions, provinces, solvers, fertility
and soil. `RunConfig.provinces=None` uses the single `province`; an empty tuple
selects no jobs. With multiple provinces, `joint=False` creates independent cases
and `joint=True` retains one combined holding in any of the three games.
`AttilaOptions` carries typed campaign inputs, region fertility overrides,
technology selections, building filters and a random seed. Explicit
`to_dict`/`from_dict` methods preserve those records across worker JSON.

`twoptimizer.constraint_options.ConstraintOptions` holds optional exact-building
requirements/exclusions, Attila minimum religious influence, and Shogun faith/contact
settings. `RunConfig.constraints` carries these through CLI/TUI requests and worker
serialization; defaults are omitted from request JSON. The CLI helper and optional
constraints dialog construct the same record. Adapters map it to each domain's
scenario. Required IDs mean at least one across a joint holding, or in each
independent case; forbidden IDs mean zero. Existing placement and modeled caps
remain enforced. Engines compile these restrictions and independently validate
returned or reused layouts. Attila merges requirements with advanced campaign
rules and province targets without discarding caller input. Report metadata and
scenario identity retain nondefault constraints so proof reuse and resume cannot
silently cross requirements.

`RunConfig.compare_constraints` opts into the shared service's two-sided solve.
`constraint_comparison.baseline_config` removes only application building and
minimum-influence requirements, preserving the rest of the scenario. Rome's
`comparison_candidates` retains candidates exposed by an explicit requirement
when that requirement is relaxed; otherwise economic candidate pruning could
make the purported baseline a different feasible set. Advanced Attila campaign
constraints remain active on both sides.

`constraint_comparison.compare_results` checks scenario/source compatibility and
uses validated incumbent incomes and solver bounds to report optimum-loss bounds.
Exact loss requires two `OPTIMAL` results. The observed incumbent difference is
kept separate and may be negative without establishing a saving. The service
stores the summary, multiset building differences and complete baseline result
in `raw.constraint_comparison`; aggregate timings/model labels cover both solves.
Each solve receives the configured time cap. An enabled comparison with no active
application requirements runs once and records an unavailable explanation.
The TUI checkbox/tab and CLI `--compare-constraints` use this same service path.
Rome resume requires unchanged comparison mode and retries unproved costs unless
the caller explicitly requests `--fill-missing`.

`twoptimizer.requests.make_jobs`, exposed through `twoptimizer.service`, resolves
province/faction identities, validates common and game-specific options, applies
research availability rules and expands the batch. `default_config` supplies the
single-case defaults. CLI commands supply their comparison defaults explicitly;
their broader default batches remain intentional. `solve_case` also validates its
single request, so direct calls and worker calls use the same rules.

`games.tw.maps.catalog` validates immutable campaign graphs against each game's
canonical region/province IDs and checks the region-to-province graph projection.
Source-specific importers retain source hashes, ID joins, geometry types and
limitations. Contact graphs remain distinct from navigation/sea routes.
`twoptimizer.holdings` owns selection and border resolution. For joint Attila and
Rome II holdings, `adjacency=None` selects the bundled map's induced province
graph; a tuple supplies custom borders and an empty tuple explicitly disables
them. Attila's explicit campaign adjacency takes precedence over map defaults,
and conflicting explicit inputs remain errors. Campaign JSON retains directed
adjacency; picker borders are two-way links. Missing/incomplete map coverage
requires an explicit override instead of silently treating every place as isolated.
`twoptimizer.province_picker` owns the optional TUI dialogs. Automatic borders
follow selections; custom borders are pruned on removal and flagged for review
on expansion. **Use map borders** restores automatic mode. `raw.map_context`
records effective borders and source evidence alongside the unchanged input
intent. CSV exports use those effective borders.

Rome II's `HoldingScenario`/`HoldingEconomy` compose the existing placement and
solver backends. Province-specific economic expressions share one political
choice, a faction food balance and recipient routing for worldwide/adjacent
building effects. Each province retains its local order constraint and income
evaluation. Single-province source fingerprints remain unchanged; joint reports
add a fingerprint for the holding modules and replay their per-province economics.

`twoptimizer.adapters` prepares the game's scenario and invokes its existing
engine. It turns the independently evaluated native report into `EngineResult`.
`solve_case` constructs `CaseResult` with income, status, objective, bound, layouts,
metrics, assumptions, source hashes and phase timings. Native dictionaries remain
at the adapter/report boundary and belong to that case. Frozen dataclasses do not
make those native reports deeply immutable. Solver upper bounds remain separate
from independently evaluated feasible income.

An optional, caller-owned `RunSession` retains Attila model preparation and
validated faction proofs, and Rome II incumbents and portable proofs. It also
checks agreement between proved optima for equivalent requests. Rome II resumes
preserve the best incumbent and strongest available bound. These services own
reuse behavior; CLI modules own loading and saving existing report formats.
Attila computes the full compiled-model signature only when proof reuse is
requested; ordinary cases avoid that extra pass over the model. Session state
never becomes process-global, and each independently compiled model owns its
decision containers.

`twoptimizer.runner` owns process creation, captured native output, progress
transport, termination and reaping. The TUI's `BatchRunner` reuses one subprocess
for sequential cases, retaining imports and immutable catalogs while building a
fresh model for each case. `CaseRunner` retains its one-shot API. The worker
decodes each request, invokes `solve_case` and atomically publishes its result or
error before acknowledging the request. It does not share incumbents or proofs
between cases. Foreground CLI cases call the same service synchronously.
Worker startup/dispatch/wall timings belong to the execution layer;
model and solver phase timings belong to the case. The first TUI cancellation
request prevents dispatch of later cases and asks the active solver to stop
gracefully. CP-SAT returns its current incumbent through the ordinary independent
validation and result-adaptation path; a validated FEASIBLE layout retains its
bound and gap. No candidate or proof produces UNKNOWN, not INFEASIBLE. An
already completed proof remains terminal.

Force stop and shutdown terminate and reap the subprocess, which may discard
the active incumbent. Earlier completed results remain available in the running
UI. The pinned OR-Tools 9.15 HiGHS native solve ignores interruption; a graceful
request stops subsequent cases but may wait for that solve to return. Temporary
files are removed during cleanup. Solver CPU
parallelism remains automatic from the machine's available allocation; the
number of selected provinces does not set the solver's thread count.

`progress.ModelStats` carries observed compilation sizes alongside string phase
events. Adapter observers return existing engine models untouched, with no extra
compilation or global monkeypatching. Rome's canonical proof model stays distinct
from its linearized search model; Attila's compact solver counts are distinguished
from its expanded validation model. The service retains these observations in
`raw.model_complexity`, preserving native `model_stats` report fields. The UI
preview expands requests only; model counts arrive through worker events and are
restored from saved results. Counts are before presolve, and sparse matrix bytes
are not an estimate of solver memory or runtime.

`progress.SearchStats` transports CP-SAT candidate income, objective bound and
elapsed search time. `games.tw.search_progress` observes native callbacks and
converts scaled objectives back to income units; adapters translate them into
application events. Delivery is throttled, with first candidate and final
observations preserved. A missing candidate remains absent, and an UNKNOWN
response's default zero is not presented as a proved bound. Model counts arrive
before search. The TUI displays search observations separately from validated
case results. A graceful CP-SAT stop can publish a candidate only after the same
independent validation used for ordinary solver completion. Its FEASIBLE status
and remaining bound gap are preserved; stopping does not manufacture an
optimality or infeasibility proof.

`runtime_view.RuntimeView` owns TUI case timing and coordinates the runtime
display without invoking solvers. `search_activity.SearchActivity` tracks best
observed candidates/bounds and advances elapsed/quiet intervals on the UI clock;
each native search resets it, including separate constraint-comparison sides.
`runtime_history.RuntimeHistory` retains bounded timing observations for exact
requests within the app session. Terminal proof statuses are distinct from
cancelled/unfinished results, and both comparison sides must be accounted for.
`runtime_evidence` reads bundled, sourced benchmark summaries and matches expanded
holdings plus scenario settings. Explicit reference-machine/build caveats cover
execution differences; none of these modules extrapolates completion from model
counts, gaps or batch case counts. They do not change solver parameters, worker
selection, cancellation or result serialization.

`ApplicationError` identifies invalid requests across direct and subprocess
execution; its message and code survive worker transport. Runtime failures remain
failures rather than solver feasibility claims. `service.error_result` constructs
the typed failed-case record used by the TUI. `twoptimizer.export` retains the TUI
session JSON/CSV schema, while the CLI modules serialize their existing native
comparison formats.

### Interface capabilities and defaults

All interfaces default to no time limit and automatic CPU selection. Explicit
`--seconds` and `--workers` remain available in the CLI. The TUI exposes an optional
time limit and uses automatic workers.
CP-SAT is the default and HiGHS is the supported alternative across all three
games. The shared HiGHS adapter consumes the linear model, retains integer domains,
and returns statuses, incumbents, bounds and conversion/search timings. Rome's
CP-SAT path retains its canonical proof model and linear product formulation.
HiGHS runs through OR-Tools MathOpt using the shared library bundled with OR-Tools;
there is no standalone `highspy` dependency. The adapter serializes its native
calls and resets the bundled HiGHS thread scheduler before each solve so changing
worker limits in a reused process takes effect. Both MIP gap tolerances are zero.
Retired solver names are rejected at current request boundaries. Historical
report labels describe their original execution and are not rewritten.

| Interface | Default scope | Additional supported inputs |
| --- | --- | --- |
| TUI | Rome II, Rome, coastal reference, CP-SAT, research disabled | Independent or joint holdings in all three games; Attila/Rome border picker; one/all factions; solver comparison; model-size details; game research profiles; Attila fertility/religion; Shogun soil, wealth and tax; Rome world bonuses |
| `attila` | ERE, Orthodox; every province independently at fertility 0 and 5; CP-SAT; all technologies | Repeated provinces and optional joint ownership/limit; campaign JSON and target constraints; named technology subset; regional fertility; city/building levels and military eligibility; CP-SAT or HiGHS; random seed |
| `attila-factions` | Settled playable factions; independent Aegyptus, Thracia and Germania; fertility 5; Orthodox; all technologies; CP-SAT | Province selection, religion, fertility, NPC factions with horde exclusions, validated proof reuse and resume |
| `rome2` | All imported factions on independent inland/coastal/grain reference layouts; CP-SAT; research bonuses disabled | Repeated named provinces/layouts, factions and solvers; public/archived research; world bonuses; resume/fill-missing, warm hints and portable proof reuse |
| `shogun2` | All imported clans jointly owning Sado, Settsu and Owari; native/barren/very fertile soil comparisons; CP-SAT; all arts | Repeated joint provinces, clans, soils and exact solvers; fixed town wealth and tax |

The TUI and the `attila`, `rome2` and `shogun2` commands also expose optional
building requirements and their income-cost comparison. Comparison remains off
unless requested; enabling it does not change the normal time-limit or CPU policy.

The shared request supports advanced CLI cases even though the TUI does not expose
all of those controls. Adding an interface option should translate into these
requests rather than introduce another engine orchestration path. Solver
mathematics, independent evaluation, bundled game data and Python 3.14 targeting
remain in their existing engine/build boundaries.

## HoI4 ingestion and planning boundaries

`games.hoi4.data_pipeline` reads source syntax and records literal facts with
source hashes and explicit diagnostics. Parsing a file does not execute its
conditions, effects or defaults. The requested latest-stable/all-gameplay-DLC
target is separate from the imported mirror's unverified patch identity.
`resolved_import` builds a separate interpretation layer from checked literal
artifacts and a pinned source checkout. Equipment inheritance, OOB selection,
initial modifiers and state/landmark summaries have their own resolvers. Guarded
official patch overlays preserve original evidence; they do not certify the
entire snapshot. Derived loaders verify individual artifact hashes. Unknown
inventory, conditional effects and designer economics remain explicit instead
of being replaced with usable-looking zero values.
`twoptimizer.hoi4_data.inspect_reference` supplies the same caller-owned report
to the `hoi4 data` CLI and TUI inspector. This read-only route does not invoke
`solve_case` or enable the historical production experiment as a campaign solver.

`games.hoi4.planning` owns the new hourly inputs. Its no-leap calendar and
half-open intervals make a deadline boundary explicit without selecting the
order in which economic subsystems update. User-approved scope is construction,
production allocation and recruitment against a supplied dated research/focus/law
plan. Model approximations and concrete objective definitions remain explicit
decisions; a parsable planning input is not proof of a playable scenario.
The current agreed objective is final usable civilian construction capacity,
subject to reserve-equipment and fully equipped, trained division deadlines.
There is no secondary spending objective. Provisional hourly efficiency
integration and training only after full equipment have been approved; their
small arithmetic helpers still require callers to supply effective rates and
eligibility, and do not constitute a complete campaign transition engine.
Construction uses simultaneous allocations from the starting hourly boundary,
with completions available at the ending boundary and an explicit overflow
policy. Consumer-goods and power arithmetic take effective pools, modifiers and
rule constants as inputs; they do not infer occupation, trade or initialization.

`ObjectiveSummary` carries ordered objectives with labels, units, direction,
value, bound and individual proof status. A proved primary objective can coexist
with an unfinished secondary objective. Overall `OPTIMAL` requires all reported
priorities to be proved, and a later priority cannot be proved before an earlier
one. `RunSession` compares proved prefixes only for matching requests, source
snapshots and objective identities. Existing Total War results omit empty
objective lists, preserving their JSON and CSV shapes.

## Regression evidence

`tests/fixtures/attila-models.json` records model signatures generated from commit
`8a5f157` before this refactor. Six scenarios cover ERE, WRE and Aksum, Orthodox
and Catholic religions, fertility 0/1/5, researched/unresearched states, and joint
provinces. The signatures cover variable names, objective coefficients, sparse
constraint coefficients, bounds and objective offset.

`tests/test_architecture.py` checks those signatures, concurrent and interleaved
compilation, cleanup after failure, typed serialization, and independent layout
validation. Existing fixture, CLI, worker, TUI and export tests remain in place.

`tests/test_application_cli.py` and `tests/test_attila_application.py` compare
CLI requests with the shared service and direct engine compilation, including
joint holdings, campaign inputs, region fertility, technology subsets and solver
bounds. Assertions compare income and proof semantics rather than timings or
building choices among tied optima. Resume tests cover validated proof replay,
negative-income incumbents and contradictory bounds.

`tests/test_application_requests.py` checks shared validation, batch expansion,
income-only inputs and typed request boundaries. `tests/test_tui_lifecycle.py`
checks direct/worker equivalence, typed campaign serialization, portable errors,
and cancellation of a real native worker while retaining a completed case and
its JSON/CSV export. Cancellation regressions also exercise native CP-SAT stops,
worker transport, retained incumbent validation, constraint comparisons and TUI
export after stopping. Force termination remains separately tested.
Upstream province-picker, border and Rome snapshot replay
regressions remain in the suite.

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

## Shared application comparison

The application-layer change was compared with `bb1f142` using Python 3.14.9,
CP-SAT, one worker and no time limit. Six serial runs per revision/game used the
UI's default economic settings; the measurement order was reversed halfway
through. Every run retained the same income, status, objective and bound. These
checks intentionally ignored timing and tied building selections when comparing
semantics.

| Game | Previous median (range), seconds | Shared-service median (range), seconds |
| --- | --- | --- |
| Attila | 0.6564 (0.6211–1.0207) | 0.6314 (0.5950–0.6676) |
| Rome II | 0.9879 (0.9742–1.0142) | 1.0313 (0.9098–1.0746) |
| Shogun 2 | 0.0132 (0.0121–0.0227) | 0.0145 (0.0116–0.0177) |

The ranges overlap. These small samples establish result preservation, not a
general speedup: Rome II's median was slightly higher, and Shogun 2 added about
one millisecond. Profiling the initial Attila adapter found approximately 0.10 s
spent computing an unused model signature; ordinary runs now skip that work,
while faction proof reuse retains the signature and independent validation.

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

## Integrated solver formulations

The concurrent `bd60b0c` solver changes are retained in this module structure.
Attila's compact income formulation keeps the expanded model as its validation
reference and reconstructs every auxiliary before checking the result. Rome's
linear products and CP-SAT import live alongside the extracted compiler/backend
modules, and proof indices still refer to the canonical model. The exhaustive
layout and warm-start regressions for those formulations remain part of the suite.

For joint Rome II CP-SAT, `joint_search` can prepare certified bounds before the
full native search. The linear holding compiler labels only the global food row
`__realm_food`; the canonical native proof model's row remains unchanged.
`decomposition` temporarily relaxes that tagged row for bound construction,
propagates fixed variables, and forms connected components using every retained
constraint. Shared variables, optional requirements and cross-province effects
therefore continue to connect groups. This is not a split based on province names.

`bound_search` uses a HiGHS continuous relaxation to suggest a nonnegative integer
food price. That price is a heuristic; the LP objective and dual are not accepted
as exact income certificates. Short CP-SAT searches and safe integer-domain
bounds establish bounds on each component's income plus priced food. The resulting
inequalities strengthen the original model, whose shared-food row stays enforced.
All fixed objective and food contributions are included when combining the upper
bounds. Unsupported integer scaling skips this preparation. Components without
a completed search retain a safe domain bound rather than an assumed optimum.

An assembled seed is eligible only after checking every original variable domain
and matrix row. The owning Rome optimizer then evaluates the final layout's
economics independently. `joint_search` retains the best available validated seed
or native candidate and strongest certified bound. A retained seed can yield
FEASIBLE when native search returns UNKNOWN or is cancelled before starting;
native OPTIMAL/INFEASIBLE proofs are not inferred from partial component results.
Reports retain the native status when it differs, bound-stage details and separate
`bound_strengthening_seconds`, conversion and final-search timings. Source
provenance includes the new modules while canonical proof identity stays separate.

Preparation is attempted only with at least four components and enough remaining
allowance. Its configured allowance is at most 40 seconds and, for limited runs,
two-thirds of the remaining overall allowance. LP pricing receives at most ten
seconds and component searches at most one second each, all sharing that same
preparation allowance. These are solver allowances, not hard wall deadlines.
The pinned HiGHS backend cannot interrupt an active pricing solve; cancellation
is checked around it, and Force stop remains available. Components are processed
serially using the same machine-derived worker allocation as the full search.
See the [method and measurements](rome-joint-bounds.md).

For holdings with at least four provinces, Attila's `compact` builder groups
factored income by province and adds independent extra-income terms directly to
the objective, avoiding artificial connections through aggregate variables.
Its `partition` module derives province ownership
recursively from reference decisions, products and indicators. Only certified
cross-province reference rows can be relaxed for preparation; indicator rows,
economic definitions and rows with unknown ownership remain. The actual native
constraint graph includes enforcement literals and product factors. `projection`
adds necessary local inequalities from relaxed rows using optimistic bounds on
external contributions and exact fixed shifts. It does not assume those external
choices are jointly attainable.
Smaller holdings preserve the original native income grouping, auxiliary
aggregation and product formulation, and skip this bound preparation.

Attila's `native_parts` extracts and independently validates supported native
components with exact integer objectives. `bound_search` combines safe component
bounds, including fixed contributions, and adds valid inequalities to the
unchanged complete model. A combined seed must satisfy every original native
constraint. `joint_search` retains valid seeds and native proof semantics, restores
expanded auxiliaries and validates the original reference matrix and objective.
It uses the same preparation caps as Rome, without an LP food-price pass.
Component searches use one native worker each and run concurrently within the
machine's allocated worker count; final joint search retains the full allocation.
Each component's allowance is at most one second, with the remaining budget
shared across the remaining waves. Reports preserve the separate preparation timing and
component statuses. See the [Attila method](attila-joint-bounds.md).

The integrated architecture was compared against `bd60b0c` with the same locked
Python 3.14 environment, default scenarios, one worker and three serial samples.
All three games produced identical result fingerprints, including income,
status, metrics and selected buildings. Observed median seconds were:

| Game | Incoming solver implementation | Integrated architecture |
| --- | ---: | ---: |
| Attila | 0.705 | 0.684 |
| Rome II | 1.034 | 0.966 |
| Shogun 2 | 0.0152 | 0.0122 |

Sample ranges overlap. These measurements show no observed slowdown on the
checked workloads; they do not establish a general speedup.
