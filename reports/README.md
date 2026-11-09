# Recorded evidence

These checked-in reports retain benchmark results, income comparisons and source
audits for their recorded inputs and revisions. Compare scenarios, model scope,
solver status, bounds, hardware and allowances before comparing numbers. Earlier
reports may describe models or source paths that have since changed; those
historical records remain intact.

Reports stay in the repository and source distribution. The installed wheel does
not include this directory. Runtime estimates use the curated evidence in
[`twoptimizer/data/runtime_evidence.json`](../twoptimizer/data/runtime_evidence.json).
For new exploratory measurements, use the ignored `benchmark-results/` directory;
retain a reviewed report here when it documents a reproducible result.

## Solver and application measurements

| Investigation | Data |
| --- | --- |
| [Architecture refactor](../docs/investigations/architecture-refactor.md) | [Model identities and installed-wheel measurements](architecture-refactor.json) |
| [Native multiplication](../docs/investigations/native-products.md) | [Measurements](native-products.json), [validation](native-products-validation.json) |
| [Joint preparation](../docs/investigations/joint-preparation.md) | [Preparation and search](joint-preparation.json) |
| [Joint scaling](../docs/investigations/joint-scaling.md) | [Full-world measurements](joint-scaling.json) |
| Joint bounds | [Attila](attila-joint-bounds.json), [Rome II](rome-joint-bounds.json) |
| [CP-SAT and HiGHS](../docs/investigations/cpsat-highs-performance.md) | [Backend comparison](holding-performance-cpsat-highs.json), [formulation comparison](solver-formulation-comparison.json) |
| [Optional constraint costs](../docs/investigations/constraint-cost-examples.md) | [Worked examples](constraint-cost-examples.json) |
| TUI batch execution | [Measurements](tui-batch-performance.json) |

The [holding baseline](../docs/investigations/holding-performance.md) documents
these earlier workload groups:

- All provinces: [Attila](holding-performance-all-attila-cpsat.json),
  [Rome II](holding-performance-all-rome2-cpsat.json),
  [Shogun 2](holding-performance-all-shogun2-cpsat.json).
- Backend and formulation samples: [paired provinces](holding-performance-pairs.json),
  [Rome II alternatives](holding-performance-rome-alternatives.json).
- Longer allowances: [Attila independent](holding-performance-sensitivity-attila.json),
  [Attila joint](holding-performance-sensitivity-attila-joint.json),
  [Rome II independent](holding-performance-sensitivity-rome2.json).

## Income and scenario comparisons

CSV files provide tables; their corresponding JSON files retain additional inputs,
results and solver evidence. These are comparisons under the recorded assumptions,
not universal rankings of civilizations.

| Scenario | Table | Details |
| --- | --- | --- |
| Attila income | [CSV](attila-income-comparison.csv) | [JSON](attila-income-comparison.json) |
| Attila fertility | [CSV](attila-fertility-comparison.csv) | [JSON](attila-fertility-comparison.json) |
| Rome II income | [CSV](rome2-income-comparison.csv) | [JSON](rome2-income-comparison.json) |
| Rome II ranking | [CSV](rome2-ranking.csv) | [JSON](rome2-ranking.json) |
| Rome II provinces | [CSV](rome2-province-comparison.csv) | [JSON](rome2-province-comparison.json) |
| Rome II resources | [CSV](rome2-resource-comparison.csv) | [JSON](rome2-resource-comparison.json) |
| Rome II research | [CSV](rome2-research-comparison.csv) | [JSON](rome2-research-comparison.json) |
| Rome II Marib | [CSV](rome2-marib-comparison.csv) | [JSON](rome2-marib-comparison.json) |
| Rome II solvers | [CSV](rome2-solver-comparison.csv) | [JSON](rome2-solver-comparison.json) |
| Shogun 2 income | [CSV](shogun2-income-comparison.csv) | [JSON](shogun2-income-comparison.json) |

## Data coverage and validation

- Rome II: [source audit](rome2-source-audit.json), [verification](rome2-verification.json)
  and [world coverage](rome2-world-coverage.json).
- Three Kingdoms: [readiness](three-kingdoms-readiness.json),
  [historical readiness](three-kingdoms-historical-readiness.json),
  [city-level cases](three-kingdoms-city-levels.json) and
  [validation](three-kingdoms-validation.json). The
  [validation narrative](../docs/investigations/three-kingdoms-validation.md)
  explains the supported model and remaining gaps.
