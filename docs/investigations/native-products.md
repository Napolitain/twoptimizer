# Native CP-SAT multiplication experiments

Native multiplication is an alternative exact formulation, not a guarantee of a
stronger relaxation or faster proof. The experiments compare the published
`e494965` baseline with native-product candidates over the same economic data,
constraints and objective. HiGHS keeps its linear formulation.

## Automatic selection

Attila uses the native variant for eligible compact-income holdings with at least
eight provinces. Its existing cubic-income eligibility remains in force: automatic
WRE/barbarian quadratic cases still use the expanded formulation. Three Kingdoms
uses native products for CP-SAT holdings with at least eight commanderies. Smaller
cases and local starting-layout preparation retain their previous formulations.
Rome II and Shogun keep their previous defaults.

This threshold is a measured search heuristic, not a promise of improvement for
every faction, requirement or map selection. The internal engine APIs retain
explicit overrides for experimentation. The CLI and TUI need no additional
setting, and their ordinary unlimited search behavior is unchanged.

## What changes in each engine

- **Attila:** the existing compact model already uses native integer products.
  The experiment also replaces its exclusive-selector branches and new Boolean
  monomials with multiplication equalities. Its expanded binary model remains the
  validation reference. Explicit experimental selection can also test quadratic
  factions normally assigned to the expanded model.
- **Rome II:** native products already form the canonical proof model. The
  experiment searches a clone of that model. Linear component preparation stays
  separate; only its certified total bound and independently reconstructed layout
  transfer into native search. Linear auxiliary-index cuts do not transfer.
- **Shogun 2:** each verified three-row Boolean AND definition becomes one native
  multiplication equality. The original inequalities already describe the local
  convex hull, so the smaller row count need not improve the relaxation.
- **Three Kingdoms:** explicitly recorded product definitions replace eligible
  bit expansions. Factors with multiple terms are materialized as bounded integer
  variables. Definitions stay linear if another retained constraint or objective
  uses their auxiliary variables. Returned native assignments reconstruct all
  removed auxiliaries and check every original linear constraint.

Independent economic validation, cancellation and applicable previous bounds
remain active. Native-model validation checks integer-domain restrictions before
search. Signed factor bounds and objective offsets are preserved; a failed model
validation is never reported as economic infeasibility.

## Repeated installed-wheel results

Both environments use locked Python 3.14.9 and OR-Tools 9.15.6755 with four
allocated CPU cores. Each run has a fresh process outside the checkout. Native
workloads run serially; the worker guards are 180 wall seconds and 4 GiB RSS.
CP-SAT seeds 0 and 1 are paired across variants, with alternating order. Parallel
HiGHS pricing does not receive those CP-SAT seeds.

The primary matrix has 32 runs: four games, single province or complete map,
default or native formulation, and two repeats. The single provinces are Thracia,
Italia, Owari and Yingchuan, using default factions and settings. Full-map
allowances are 60 seconds for Attila and Rome II, 30 for Three Kingdoms and 20 for
Shogun. These are measurement limits; normal application runs remain unlimited.

| Full-map CP-SAT case | Baseline gap | Native gap | Observation |
| --- | ---: | ---: | --- |
| Attila, 62 provinces | 5.26–6.18% | 2.98–4.14% | Higher validated income and tighter bounds in both repeats |
| Rome II, 57 provinces | 1.35%, or no candidate | 1.01–1.68% | Mixed; one baseline pricing stage timed out |
| Three Kingdoms, 70 commanderies | 9.04–10.54% | 3.06–8.04% | Higher validated income and tighter bounds in both repeats |
| Shogun 2, 65 provinces | 0%, OPTIMAL | 0%, OPTIMAL | Small overlapping timing ranges |

None of the full-map Attila, Rome II or Three Kingdoms measurements proves
optimality. Their improved gaps describe result quality within a fixed allowance,
not a measured reduction in time to proof. Wall times remain approximately
77–78 seconds for Attila, 63 for Rome and 31 for Three Kingdoms, including model
preparation and validation. Shogun proves the same 84,071.498 income in
3.17–3.73 seconds at baseline versus 3.08–3.39 with native Boolean products.

Full-map peak RSS is 1,539–1,615 MiB versus 1,480–1,542 for Attila; 780–987 versus
1,004–1,162 for Rome; 408–439 versus 397–421 for Three Kingdoms; and 147–150 versus
147–152 for Shogun. These ranges are two observations, not confidence intervals.

Rome's single Italia case favors the linear default: it proves income 9,733.80
within both ten-second allowances. Native products find that same income but
finish with approximately 19.4% gaps. This is a concrete counterexample to
assuming native products always strengthen the proof.

Rome's linear pricing inputs and preparation policy are shared by both paths.
Native search moves linear compilation into the reported preparation phase,
so individual phase labels are not directly comparable; total wall time is.
One baseline pricing timeout caused incomplete component preparation and no
validated final layout. That outcome is retained, but the timeout-to-success
change is not attributed to multiplication equalities, which are absent from
the pricing LP.

The deterministic serialized pricing-model hashes were subsequently compared:
both are `5353953feb943249857d3b0ef5e665fe423ef8831f8b124f497842cd0e5bdcac`, with
22,982 variables, 46,265 linear rows and the same ten-second pricing allowance.

## Intermediate holding sizes

Sixteen additional paired runs check two/eight Rome provinces, eight Attila
provinces and eight Three Kingdoms commanderies. Rome and Attila retain sixty-second
allowances, so preparation remains eligible; Three Kingdoms retains thirty.
The exact named holdings are recorded in the report.

- Attila's eight-province gaps improve from 3.10–5.25% to 1.55–2.87%, and peak RSS
  falls from 638–726 MiB to 357–486 MiB. Income is slightly lower in one native
  repeat and higher in the other: 197,929.38–199,024.00 versus
  197,102.21–198,783.44. This tradeoff is retained alongside the full-map gains.
- Three Kingdoms' eight-commandery native income is 7,870.75 in both repeats,
  versus 7,797.00–7,804.50. Gaps improve from 5.74–5.84% to 4.78–4.86%, and RSS
  falls from 236–243 MiB to 211–212 MiB.
- Rome's two-province native gaps are 19.39–19.62%, versus 11.93–12.67%; its
  eight-province gaps are 13.01–13.54%, versus 11.93–12.65%. Native incomes are
  slightly higher in three of these four comparisons, but it consistently has
  weaker bounds. Together with Italia and the mixed full-map results, this
  supports retaining the current default.

The [measurement report](../../reports/native-products.json) retains all 48 outcomes.
The [validation report](../../reports/native-products-validation.json) records the
independent optimal-income checks, pricing identity and final application checks.

## Validation and reproduction

All 70 independent Three Kingdoms commanderies were solved with native products
and matched the previously proved incomes. Focused tests cover signed and nested
products, Boolean truth tables, retained external auxiliary references, corruption,
reference constraint enforcement, bound transfer and cancellation. Rome's native
assignment mapping explicitly handles constants inserted by CP-SAT.

Build each version with `uv build`, then install its wheel into a separate
Python 3.14 environment with the same locked production dependencies. Copy
`tools/native_product_benchmark.py` outside the checkout and run:

```sh
python native_product_benchmark.py \
  --baseline-python /path/to/baseline/bin/python \
  --native-python /path/to/candidate/bin/python \
  --output native-products.json
```

For this comparison, install revision `e494965` in the baseline environment.
The tool's `default` variant means that environment's actual default. Using the
new release in both environments will exercise automatic native selection on
both sides for eligible Attila and Three Kingdoms holdings.

Use `--game rome2 --scope pair --scope eight --joint-seconds 60` for intermediate
holding sizes. Keeping at least 45 seconds available permits the existing Rome
and Attila joint preparation. Shorter tests can skip it and should not determine
an unlimited-run policy by themselves.

The measured primary driver starts its wall clock immediately after `Popen`,
including imports and preparation but excluding the launch call. The later
supplemental driver also includes launch-call overhead and improves failure
recording; solver selection and mathematics are unchanged. The report preserves
their exact source text and hashes, wheel digests, source fingerprints, every
outcome and the observed progress milestones. Raw trace samples and full worker
layouts remain in the recorded local artifact directories and can be regenerated.
