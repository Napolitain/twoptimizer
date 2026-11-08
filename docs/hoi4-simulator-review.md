# HoI4 simulator reuse review

Checked `Napolitain/hoi4simulator` through the GitHub connector on November 8,
2026. Its latest `main` is still
[`d84dbd97a04eab411df7f79eb85589aa2b42fbc5`][commit], April 6, 2026.
This was a source review; its Rust build, tests and planner were not run.

## Available data

The complete, non-truncated Git tree has 44 tracked files and **no tracked game
dataset, JSON/CSV/TSV export or Fory snapshot**. The [ignore file][ignore]
excludes `data/raw/` and `data/structured/`. The [installed-data loader][loader]
expects the user's game directory, mirrors selected files, and writes
`manifest.fory` plus `scenarios/france_1936.fory`. Those local artifacts are not
recoverable from the public repository.

There are useful test cases and a curated France bootstrap in Rust source.
They are distinct from verified installed-game data:

| Source | What is actually available | Use here |
| --- | --- | --- |
| [`France1936Scenario::standard()`][scenario] | Twelve curated states, 42 civilian factories, 16 military factories, population 41 million and hand-chosen production lines. | Example workload and test-design reference; not the current France starting state. |
| Data-loader unit tests | Small Clausewitz fixtures constructed in temporary directories, including inheritance, DLC branches and OOB references. | Ideas for independent boundary tests. |
| Installed-data ingestion | Parsing and mapping code, including raw state IDs, OOB selection, technology/focus/idea loading and fielded-force reconstruction. | Review its field coverage; obtain actual values from our pinned sources or a later installed export. |
| Normalized Fory schema | State, laws, production-line and equipment-profile schema definitions. | Architectural comparison; no populated dataset to import. |

The loader does reconstruct existing divisions from OOB template references and
`start_equipment_factor`. An earlier shorthand suggesting that it had no
existing-army support was too broad. The limitation is that its demand mapping
is hardcoded and incomplete, rather than derived from the source unit catalog.

## Clean design ideas to adopt

| Simulator pattern | Application in twoptimizer |
| --- | --- |
| Separate source loading, scenario, runtime, actions and search | Keep our syntax/provenance import separate from rule resolution; produce an immutable resolved scenario before allocating mutable hourly state. |
| Explicit dated action records | Use typed hourly actions shared by search, replay, CLI and TUI. Validate ordering, identifiers and duplicate/conflicting assignments at the replay boundary. |
| Raw and dense identifiers coexist | Keep exact equipment/state identifiers in the catalog and reports. Compile optional dense indices for runtime arrays with a reverse map. Names are display data, not identity. |
| Planner candidates are replayed by the simulator | Require every proposed solution to pass the same deadline/readiness validation used for user-authored plans. Keep engine execution independent of the search strategy. |
| Action-state exports | Report available civilian capacity, queues, production, equipment deficits and active modifiers alongside action times, with source IDs that users can recognize in game. |
| Explicit unsupported-condition/effect errors | Retain our stronger unknown/unsupported diagnostics throughout scenario resolution and execution. A parsed script must not silently become executable. |

The simulator's [typed actions][actions] and `CountryScenario` trait are useful
separation ideas, but its current [simulation engine][engine] still takes `France1936Scenario`
specifically. We should make the actual engine boundary country-independent,
using the same resolved scenario shape for all eight supported countries.

The [action-state export][exports] currently replays from the beginning for each
action date. Its output concept is useful; our hourly engine should capture
snapshots during one replay or from validated checkpoints. That avoids repeated
work without changing game rules. Dense IDs likewise belong in compilation,
after source validation, and should not inherit its `u8` state limit: our source
inventory already contains 1,081 states.

## Mappings and assumptions to replace

- **Equipment identity:** the loader groups raw tokens using string prefixes.
  `light_tank_chassis_1` does not match its legacy tank-equipment prefixes and
  becomes `Unmodeled`. Preserve raw IDs and declared relationships instead of
  using this classification as eligibility or costing.
- **Inheritance:** `resolve_equipment_profile` chooses `parent` before
  `archetype`, substitutes zero resources if unresolved, and other paths fall
  back to normalized costs or a pre-1936 equipment type. It also deduplicates
  definitions. Our dependency graph keeps all declarations and the separate
  relationships; the new [base equipment resolver](hoi4-equipment-resolution.md)
  follows sourced archetype inheritance while preserving unresolved designer economics.
- **Template demand:** `add_regiment_demand` adds 1,000 infantry equipment per
  infantry battalion, whereas our imported unit source declares 100. It also
  hardcodes support requirements and cannot cover all source unit types. Read
  `sub_units.need` and template entries instead of copying these tables.
- **History scope:** its generic history visitor recursively enters arbitrary
  child blocks; its DLC helper ignores unknown predicates and defaults an
  entirely unknown condition to true. Our selection boundary must keep scope
  and unknown conditions explicit, including when known DLC tests also occur.
- **Runtime rules:** its default infrastructure cost is 3,000 IC and efficiency
  growth is a fixed five permille per day. Its [resource enum][resources] excludes coal.
  These conflict with the current sourced rules/data or omit required mechanics;
  they cannot establish the agreed latest-stable hourly model.
- **Search objective:** its [France beam planner][planner] uses weighted scores and
  strategy/pivot heuristics. Those can inspire candidate generation, but they
  do not implement our objective of maximizing final civilian construction
  capacity subject to military deadlines, nor prove optimality. There is no
  secondary delayed-spending objective.

## Fit with the current import

Our country profiles retain declared state histories, selected source branches,
candidate OOBs, templates, production fields and source diagnostics. The
equipment catalog retains raw costs/resources, unit needs and generated-archetype
declarations. Hashes and locations make those facts inspectable. This is a
better input boundary for the simulator's useful separation of catalog and
runtime than adopting its already-defaulted France dataset shape.

The immediate engineering improvement is indexed source lookup at that boundary:
`Document.position` already has a cached line index, so importer source-line
mapping now uses it instead of rescanning the full text for every declaration.
The existing importer provenance and deterministic-rebuild tests verify this
change. No gameplay behavior or external simulator code was copied; no application
speedup is claimed without a representative benchmark.

The next engine interface should accept a resolved scenario, an explicit rules
profile, ordered hourly actions and a stop time, and return a replay outcome
with violations and snapshots. A planner can produce candidate actions through
that interface. The existing shared request/result and inspector layers remain
the application boundary. Do not add a second France-specific CLI, import the
simulator's binary format, or introduce its heuristic assumptions as defaults.

Remaining data and rules work is tracked in
[starting-scenario gaps](hoi4-starting-scenario-gaps.md). This review supplies
design and mapping evidence; it does not turn the incomplete source snapshot
into a validated game scenario.

[commit]: https://github.com/Napolitain/hoi4simulator/commit/d84dbd97a04eab411df7f79eb85589aa2b42fbc5
[ignore]: https://github.com/Napolitain/hoi4simulator/blob/d84dbd97a04eab411df7f79eb85589aa2b42fbc5/.gitignore
[loader]: https://github.com/Napolitain/hoi4simulator/blob/d84dbd97a04eab411df7f79eb85589aa2b42fbc5/src/data/france_1936.rs
[exports]: https://github.com/Napolitain/hoi4simulator/blob/d84dbd97a04eab411df7f79eb85589aa2b42fbc5/src/bin/france_1936.rs
[scenario]: https://github.com/Napolitain/hoi4simulator/blob/d84dbd97a04eab411df7f79eb85589aa2b42fbc5/src/scenario/france_1936.rs
[actions]: https://github.com/Napolitain/hoi4simulator/blob/d84dbd97a04eab411df7f79eb85589aa2b42fbc5/src/sim/actions.rs
[engine]: https://github.com/Napolitain/hoi4simulator/blob/d84dbd97a04eab411df7f79eb85589aa2b42fbc5/src/sim/engine.rs
[resources]: https://github.com/Napolitain/hoi4simulator/blob/d84dbd97a04eab411df7f79eb85589aa2b42fbc5/src/domain/resources.rs
[planner]: https://github.com/Napolitain/hoi4simulator/blob/d84dbd97a04eab411df7f79eb85589aa2b42fbc5/src/solver/france.rs
