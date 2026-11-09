# Documentation

Start with the [quick start](../README.md) and [usage and model reference](usage.md)
for the CLI, terminal workbench, supported constraints and game assumptions.
The [architecture guide](architecture.md) describes the application, solver and
game boundaries. Checked-in measurements are indexed in [reports](../reports/README.md).

## Game models

- [Rome II](../games/tw/rome2/README.md), [Shogun 2](../games/tw/shogun2/README.md)
  and [Three Kingdoms](../games/tw/three_kingdoms/README.md) document their economic
  models and data coverage. [Attila](usage.md#run-attila) is covered in the shared
  usage reference.
- [HoI4](../games/hoi4/README.md) documents source ingestion and the hourly planning
  foundation. [Starting-scenario readiness](hoi4/hoi4-starting-scenario-gaps.md)
  identifies what is still needed before complete campaign optimization.

## Total War investigations

These records explain model decisions and measurements for their recorded inputs
and revisions. Their timings are evidence for those workloads, not predictions
for every machine or scenario.

| Topic | Records |
| --- | --- |
| Earlier architecture changes | [Ownership, application and solver measurements](investigations/architecture-history.md) |
| Joint solving and reuse | [Preparation](investigations/joint-preparation.md), [scaling](investigations/joint-scaling.md), [Rome II bounds](investigations/rome-joint-bounds.md), [Attila bounds](investigations/attila-joint-bounds.md) |
| Formulations and performance | [Native multiplication](investigations/native-products.md), [CP-SAT and HiGHS](investigations/cpsat-highs-performance.md), [holding baseline](investigations/holding-performance.md) |
| Constraints and validation | [Constraint costs](investigations/constraint-cost-examples.md), [Three Kingdoms validation](investigations/three-kingdoms-validation.md) |
| Special-building evidence | [Attila](investigations/attila-special-audit.md), [Rome II](investigations/rome-special-audit.md) |

## HoI4 references

| Topic | Records |
| --- | --- |
| Rules and readiness | [Rules review](hoi4/hoi4-rules-review.md), [scenario gaps](hoi4/hoi4-starting-scenario-gaps.md), [simulator reuse review](hoi4/hoi4-simulator-review.md) |
| Sources and imports | [Public data](hoi4/hoi4-public-data.md), [source ingestion](hoi4/hoi4-source-ingestion.md) |
| Resolved starting data | [Equipment](hoi4/hoi4-equipment-resolution.md), [modifiers](hoi4/hoi4-modifier-resolution.md), [armies and production](hoi4/hoi4-starting-armies.md) |

The [architecture refactor validation](investigations/architecture-refactor.md)
records model identities, installed-wheel comparisons and measured regressions.
