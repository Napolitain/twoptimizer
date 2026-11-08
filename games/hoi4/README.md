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
and unresolved mechanics are tracked in the [rules review](../../docs/hoi4-rules-review.md).
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
These are literal declarations from a pinned public mirror, not validated
starting capacities. A separate partial date/DLC selection records candidate
statements; effects and inheritance remain unevaluated. The mirror's exact patch is unverified and France's
order-of-battle files contain a malformed tail; diagnostics preserve that gap.

JSON inspection includes `base_requirements` for each candidate template, with
per-unit source evidence and unknown values retained. The source's
`FRA_1936.txt` infantry division has nine infantry battalions, artillery support
and engineers: **910 rifles, 12 artillery, 30 support equipment, 9,600 manpower
and 120 base training days**. These are base requirements; modifiers, equipment
substitutions, eligibility and actual training progress remain unresolved.

See [public data and reproducible imports](../../docs/hoi4-public-data.md) for
sources, hashes, coverage and independent comparisons. The selected target's
version and DLC setup do not certify the source snapshot.
The [starting-scenario audit](../../docs/hoi4-starting-scenario-gaps.md) records
which remaining gaps need source interpretation or actual game validation.

## Implementation foundations

- The [Clausewitz ingestion pipeline](../../docs/hoi4-source-ingestion.md) preserves
  repeated keys, scopes, operators, source positions and unknown statements.
- [Hourly time](planning/README.md) uses an explicit 365-day, no-leap calendar,
  integer hours and exact deadline boundaries.
- The provisional hourly arithmetic advances factory efficiency and recruitment
  progress with explicit rates and equipment/manpower gates. These helpers are
  independently tested; they are not yet a complete campaign replay or solver.
- Shared application results support ordered objectives, individual bounds and
  proof statuses without relabelling HoI4 objectives as Total War income.
- Reference inspection uses the same application view model in the CLI and TUI.

The [HoI4simulator review](../../docs/hoi4-simulator-review.md) identifies reusable
loader and replay design ideas, and the hard-coded assumptions that need replacing.

Run focused checks with the locked Python 3.14 environment:

```sh
uv run --frozen pytest tests/test_hoi4_hourly_time.py tests/test_hoi4_data_pipeline.py tests/test_hoi4_public_import.py tests/test_hoi4_data_interfaces.py --no-cov
```

## Legacy experiments

The existing `models/`, `optimization/`, phase summaries and demonstration
scripts are retained for compatibility. They are historical experiments, not
validated latest-version gameplay or the new hourly planner.

In particular, the old HiGHS production LP uses a fixed 55% average efficiency;
its separate production-line class uses a different linear ramp. Neither proves
that construction, recruitment or stockpile deadlines are achievable in the
game. The old faction examples contain only a few illustrative states. Their
phase-completion claims must not be interpreted as current campaign coverage.
