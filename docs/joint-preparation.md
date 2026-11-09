# Joint preparation and reusable search

The application can start a joint search with a previously validated layout or
prepare one from smaller problems. A valid layout gives a lower bound on maximum
income. Its income is recalculated under the complete holding's effects and
constraints before use. Independent optima are not automatically compatible:
unique buildings, resources, shared food and global requirements can conflict.

Preparation is automatic. Small cases and short search allowances can skip fresh
local searches, while compatible cached layouts remain useful. No new user time
budget or worker setting is required. An unlimited final search remains unlimited.
Preparation is not guaranteed to improve wall time or time to optimality.

## Three Kingdoms

The compiler derives safe expression bounds from mandatory settlement and port
choices, exclusive building chains and available district slots. It combines
duplicate contributions before bounding, retains signed coefficients and allows
unselected optional chains. These narrower domains strengthen the exact product
formulation without changing the selected-building economics.

Resource availability is guaranteed only when every eligible alternative of an
exactly-one settlement or port provides it, or the scenario supplies it externally.
The all-map default guarantees tea this way, eliminating 70 redundant prerequisite
rows. Five optional resource prerequisites remain. A lower tier lacking a resource
prevents this simplification; it is not a blanket assumption about map ownership.

Joint preparation first tries matching cached independent layouts and validates
their combination. A fresh pass is eligible for at least four commanderies when
at least 20 configured seconds remain, or for unlimited runs. Its total allowance
is at most 30 seconds and 60% of the remaining configured allowance. Local seed
construction can use up to 75% of that preparatory allowance. Local cases omit
global required-building targets and receive no external food; the resulting
complete layout must still satisfy the original global targets and food balance.

For CP-SAT, the bound stage temporarily relaxes only tagged shared-food and optional resource
prerequisite rows. Every other row determines the actual connected components,
including income products and factionwide silk and spice bonuses. It uses the
existing exact integer partitioner and food-price estimation machinery. Original
shared requirements stay in the final model; only valid component inequalities
are added. Unfinished components retain safe domain bounds.

For a nonnegative food price, maximizing income plus priced food over a relaxation
provides an upper bound after subtracting the priced food requirement. Fixed
income and food contributions are retained. Local feasible income is never used
as an upper bound. If the continuous relaxation cannot provide a price, the
objective and food domain widths supply a unit-aware heuristic. The chosen price
is recorded separately from the certified component bounds. Added constraints
have unique names for compatibility with OR-Tools MathOpt.

Fresh HiGHS preparation stops after obtaining the validated seed, leaving more of
the allowance for its native MIP search. It can still retain a matching cached
bound from an earlier run. A measured intermediate variant that also supplied
CP-SAT component cuts spent too much of HiGHS' allowance in preparation; the
backend-specific policy avoids imposing that extra stage.

The best independently validated layout is retained if native search returns
UNKNOWN or a worse candidate. Cancellation can retain it too. Partial preparation
does not fabricate OPTIMAL or INFEASIBLE status. A native proof contradicting a
validated layout raises an error rather than silently replacing either claim.

## Shogun 2, Rome II and Attila

Shogun 2 first tries cached layouts, including compatible independent cases. Fresh
preparation is eligible for at least four provinces with at least eight configured
seconds remaining, or unlimited runs. It receives at most five seconds and 20%
of the remaining allowance. It conservatively reserves faction-unique buildings
for final joint search and prevents independent cases from each spending the same
positive factionwide arts-food credit. Global required-building scenarios skip
this fresh pass. The complete original evaluator and binary constraints must
accept the assembled seed; final search retains all original building choices.

Rome II and Attila retain their existing component-bound and validated-seed paths,
documented in [Rome joint bounds](rome-joint-bounds.md) and
[Attila joint bounds](attila-joint-bounds.md). No additional full independent pass
is imposed on those models. In particular, Attila's food requirements remain
provincial. Repeated Attila searches now also retain independently checked prior
candidates and applicable bounds, mapping reference decisions into the compact
native model when used.

## Repeating or cancelling a run

The terminal application retains its batch worker after normal completion and
graceful cancellation. Pressing Run again reuses bounded game-specific session
state. Each game cache retains at most 128 cases or proofs, enough for the named
independent-province batches. Worker state is discarded on Force stop, Quit or
unmount. Requests receive separate cancellation markers.

Reusing a layout always requires validation against the requested game model.
Reusing an upper bound additionally requires the same mathematical model identity.
Application sessions invalidate the affected game's caches when source/data
fingerprints change. Changing scenario settings cannot silently reuse an
inapplicable certificate. Arrays, report dictionaries and layout containers are
owned by their session rather than shared with caller-mutable exports.

This reuses candidates, bounds and prepared data; it does not serialize or resume
a native solver's internal branch-and-bound tree. Solver comparisons still check
matching proven objectives. No guarantee is made that a restarted search proves
optimality sooner than a fresh run.

## Search evidence

Reports retain `raw.search_measurements`: up to 128 structured samples and 16
streams, first-observed candidate times and observed 10%, 5%, 2% and 1% gap
milestones. Milestones survive sample thinning. The case clock includes
preparation and excludes worker startup; native search clocks are stored
separately and may restart between stages. The benchmark's active-case clock
instead includes worker dispatch/startup and is explicitly labeled.

Live candidates have not necessarily completed independent layout validation.
The final validated result is recorded separately. The Runtime tab shows saved
milestones and available decomposition component counts and largest-group sizes.
HiGHS paths without native progress callbacks can have a final result without a
live candidate trace. None of these observations is an estimated completion time.

## Matched installed-wheel measurements

The [raw report](../reports/joint-preparation.json) compares baseline `11004f2`
with the candidate identified by source hashes and wheel digest. Both wheels ran
outside the checkout with the same locked Python 3.14.9/OR-Tools 9.15.6755
dependencies, four allocated CPUs, fresh workers, startup included, a 120-second
wall guard and a 4 GiB worker-memory guard. Native workloads ran serially. Each
workload has two repeats; no warmup sample was discarded.

Three Kingdoms uses all 70 commanderies, Cao Cao, automatic city levels, one
million people per commandery, zero corruption, no reforms or external resources,
and the original leader profile. Shogun uses all 65 provinces with default Oda
settings. Limits below are explicit benchmark allowances; normal runs remain
unlimited. Ranges cover the two observations, not confidence intervals.

| Workload | Allowance | Baseline income | Candidate income | Baseline gap | Candidate gap |
| --- | ---: | ---: | ---: | ---: | ---: |
| Three Kingdoms, CP-SAT | 30 s | 57,362.25–59,750.25 | 66,727.00–67,002.75 | 40.48–45.32% | 8.99–9.37% |
| Three Kingdoms, HiGHS | 30 s | 71,504.25–71,779.25 | 72,197.75 | 14.19–14.52% | 5.98% |
| Shogun 2, CP-SAT | 20 s | 83,908.998–84,071.498 | 84,071.498 | 0.72–0.91% | 0%, OPTIMAL |

Three Kingdoms remains FEASIBLE in every complete-model measurement. CP-SAT wall
time remained about 30.8 seconds; HiGHS was about 31.0 seconds before and
31.2 seconds after. These show solution/bound quality within comparable allowances,
not faster completion to optimality. Shogun proved its optimum in 3.37–4.42 seconds
including startup; the baseline remained FEASIBLE after 21.30–21.38 wall seconds.

Three Kingdoms CP-SAT peak worker memory increased from 319–340 MiB to 441–447 MiB.
HiGHS decreased from 378–407 MiB to 362–367 MiB, and Shogun from 241–242 MiB to
146–171 MiB. Three Kingdoms' base linear model shrank from 10,404 variables /
17,587 rows to 9,410 / 15,529 before component cuts. In the measured CP-SAT runs,
relaxing six shared rows exposed 72 components, the largest with 425 variables.
Both validated local seeds earned 63,030.75; final search improved them further.

For the same Three Kingdoms model, the separate final HiGHS income and CP-SAT
upper bound together give the interval [72,197.75, 73,622.86], a 1.94% gap. This
combines two separate 30-second allowances; it is not a 30-second portfolio
measurement. Matching-model session reuse can carry these candidates and bounds
between backends without treating the bounds as applicable to other scenarios.

The report preserves rejected intermediate measurements: duplicate component
constraint names failed MathOpt validation, and a missing LP price fell back to
zero and produced a weak bound. The final version fixes names, records pricing
outcomes, uses a unit-aware fallback and reserves fresh component cuts for CP-SAT.
The forced-price-fallback diagnostic remained conservative; it was not used as
one of the matched repeats. No new full-world speed claim is made for Attila or
Rome II in this change.

Separate final-wheel validation checks all 70 independent Three Kingdoms cases
with both backends against the previous proved incomes, a real all-map graceful
cancel followed by a short rerun retaining the same worker and layout, and two
real TUI runs followed by worker cleanup. These checks are separate from timing
comparisons and do not establish agreement with an installed game.

To reproduce, build each revision using `uv build`, install its wheel with locked
production dependencies in a separate Python 3.14 environment, and extract the
embedded driver files from the report into a directory outside the checkout.
Copy the matching `uv.lock` there. Run `measure.py --revision LABEL --output PATH`
with each environment's Python, followed by `shogun_repeat.py OUTPUT` for the
second Shogun sample. Run variants serially and keep every outcome. The original
benchmark driver is embedded unchanged for both revisions; newer repository
tooling additionally records structured live traces.
