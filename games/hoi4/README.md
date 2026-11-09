# Hearts of Iron IV

The new HoI4 planner targets **latest stable vanilla with all gameplay DLC**.
The verified target is 1.19.4, November 5, 2026 hotfix, checksum `0bdb`.
The hourly campaign optimizer is under development; it is not yet available
through the application's Run action.

## Agreed planning problem

The optimizer must meet equipment and fully equipped division deadlines, with
recruitment training completed for specified templates. Equipment targets mean
reserve stockpile after the divisions are equipped. Among feasible plans,
maximize civilian construction capacity at the final deadline; there is no
secondary spending objective. Construction, production allocation and recruitment are decisions;
research, focuses and laws come from an explicit dated input schedule.

Gameplay choices and approximations require the user's decision. Public evidence
and unresolved mechanics are tracked in the [rules review](../../docs/hoi4/hoi4-rules-review.md).
The first model may use the approved provisional hourly integration of the
documented production-efficiency curve and start recruitment training only when
a division is fully equipped. These approximations do not establish exact engine behavior.
Completing recruitment training means the game's **Trained** level; reaching
**Regular** additionally involves field exercises. Those are separate mechanics.

## Inspect public data now

From the repository root:

```sh
uv run --locked twoptimizer hoi4 data --country FRA
uv run --locked twoptimizer hoi4 data --country all --json --output hoi4-data.json
uv run --locked twoptimizer hoi4 plan-check my-plan.json
uv run --locked twoptimizer
```

In the TUI, select HoI4 and **Inspect HoI4 data…**. Browse countries and states
using clicks or arrow keys; Esc closes the inspector. The source tab reports
version provenance, coverage and parse failures.

`plan-check` validates a supplied [planning contract](planning/README.md) and
reports its hourly horizon, equipment/division targets and dated decisions. It
checks input structure, not deadline feasibility.

The bundled reference covers France, United Kingdom, United States, Germany,
Italy, Japan, Soviet Union and China. It contains 487 owned-state records,
308 equipment declarations, 157 unit definitions and 55 building definitions.
These literal declarations now have a derived interpretation layer: 456 equipment
IDs (440 resolved base costs/resources), 507 selected deployed divisions, initial
national economic modifiers, base state capacities/resources and conditional
landmark effects. Ten guarded official patch corrections supplement the source.
These are not validated starting capacities. The mirror's exact patch is unverified and France's
order-of-battle files contain a malformed tail; diagnostics preserve that gap.

JSON inspection includes `base_requirements` for each candidate template, with
per-unit source evidence and unknown values retained. The source's
`FRA_1936.txt` infantry division has nine infantry battalions, artillery support
and engineers: **910 rifles, 12 artillery, 30 support equipment, 9,600 manpower
and 120 base training days**. These are base requirements; modifiers, equipment
substitutions, eligibility and actual training progress remain unresolved.

See [public data and reproducible imports](../../docs/hoi4/hoi4-public-data.md) for
sources, hashes, coverage and independent comparisons. The selected target's
version and DLC setup do not certify the source snapshot.
The [starting-scenario audit](../../docs/hoi4/hoi4-starting-scenario-gaps.md) records
which remaining gaps need source interpretation or actual game validation.

## Implementation foundations

- The [Clausewitz ingestion pipeline](../../docs/hoi4/hoi4-source-ingestion.md) preserves
  repeated keys, scopes, operators, source positions and unknown statements.
- [Hourly time](planning/README.md) uses an explicit 365-day, no-leap calendar,
  integer hours and exact deadline boundaries.
- The provisional hourly arithmetic advances factory efficiency and recruitment
  progress with explicit rates and equipment/manpower gates. These helpers are
  independently tested; they are not yet a complete campaign replay or solver.
- [Construction and economy arithmetic](planning/construction-economy.md) handles
  simultaneous hourly construction, capacity and infrastructure limits, consumer
  goods, and coal-era output penalties with explicit inputs and overflow policy.
- Shared application results support ordered objectives, individual bounds and
  proof statuses without relabelling HoI4 objectives as Total War income.
- Reference inspection uses the same application view model in the CLI and TUI.

The [HoI4simulator review](../../docs/hoi4/hoi4-simulator-review.md) identifies reusable
loader and replay design ideas, and the hard-coded assumptions that need replacing.

Run focused checks with the locked Python 3.14 environment:

```sh
uv run --frozen pytest tests/games/hoi4 --no-cov
```

## Code layout

`data_pipeline/` owns source syntax, provenance and explicitly supported
interpretation. `planning/` owns the hourly calendar, planning contract and
independently tested mechanics. `cli.py` connects the supported commands to the
shared application; the CLI and TUI use the same data inspection interfaces.
Maintained tests live in `tests/games/hoi4/`.

The earlier static production LP, illustrative country models and demonstration
scripts have been retired. Their fixed efficiency and calendar assumptions are
not part of the hourly planner. The bundled source snapshots remain available
to the ingestion pipeline with their original bytes and provenance.
