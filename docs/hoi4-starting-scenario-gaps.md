# HoI4 starting-scenario readiness

The requested target is latest stable vanilla with all gameplay DLC. Online
sources now supply substantial interpreted data for France and seven other major
countries. The bundled reference remains a **partial scenario**, not an executable
or target-patch-certified campaign. See [public data](hoi4-public-data.md) for
counts and rebuild commands, and [rules review](hoi4-rules-review.md) for version
evidence and the user-approved model scope.

## What is implemented

The pinned [public source][source] contains country/state histories, equipment,
units, OOBs, technologies, ideas, designer modules, industrial organizations and
initialization scripts. A separate derived layer interprets supported semantics
while preserving literal inputs, exact hashes, corrections and unresolved fields.

| System | Implemented result | Remaining boundary |
| --- | --- | --- |
| Date and DLC selection | Explicit January 1, 1936 noon, all catalogued gameplay DLC, normal campaign rather than tutorial; unknown predicates remain blockers. | Arbitrary state scopes, initialization scripts and runtime effect ordering are not executed. OOB coverage is limited to the imported 1936 candidates. |
| Equipment | Archetype inheritance and supported duplicate-archetype expansion produce 456 IDs; 440 have resolved base IC and resource needs. | Partial resource-map overrides and some definitions remain unknown. Base chassis economics are separate from complete designs. |
| Designer variants | Selected variants retain module/upgrade economic declarations, validated upgrade levels and noncumulative resource-threshold selections. | Combined modifier order, rounding, default modules, eligibility and MIO effects require further resolution. |
| Existing army | All eight selected land rosters resolve: 507 divisions with base template equipment/manpower requirements and training times. | Actual issued manpower, fractional equipment rounding, substitutions and combat readiness remain separate. |
| Production | Selected land, air and naval lines retain requested factories, efficiency, progress, variants and source evidence. | Requested factories can include queued assignments. Effective allocation, designer/MIO economics and omitted initialization defaults remain unresolved. |
| Starting laws and modifiers | All eight selected national modifier sets resolve, including researched technology contributions, German MEFO variables, Soviet adviser traits and Chinese unset-variable defaults. Japan's equipment-specific cost bonuses retain their scopes. | This completion flag covers the selected source subsystem. It does not certify the whole effective economy or execute future law/research hooks. |
| States and landmarks | Base factory counts, category slots, occupied shared slots, deposits and core population; conditional landmark effects with three-valued controller/DLC eligibility. | Effective slots, extraction, occupation, ownership changes, damage, resource rights and usable factory pools require additional effects. |
| Stability and war support | Sourced endpoint tables, documented stability interpolation and wartime stability penalty; explicit input values. | Effective stability reconstruction and undocumented interior war-support interpolation are not guessed. |
| Hourly arithmetic | No-leap calendar; provisional production efficiency and recruitment; simultaneous construction; consumer-goods and coal-era output accounting. | Helpers take explicit effective inputs and do not yet form one complete campaign replay. Construction overflow policy and update conventions are explicit. |
| Interfaces | CLI and TUI share the same raw/derived inspection report, including Army and Economy tabs. | Campaign Run remains unavailable until scenario initialization, replay and optimization are connected. |

Ten guarded corrections from official 1.19.3/1.19.4 notes supplement the pinned
August source. They do not establish that every file matches the November target.
The exact source patch and its vanilla fidelity remain unverified.

## Starting inventory is the main initialization gap

Template requirements, equipment allocation targets and reserves are different
quantities. The selected France army requires 56,130 rifles, 420 artillery,
950 support equipment, 1,320 light tanks and 2,505 motorized equipment at base full
strength, with 579,000 manpower. These are requirements, not starting stockpiles.

The source also initializes train/truck buffers relative to logistics needs.
Country train-buffer declarations and starting convoys are preserved, but buffer
override, network need and rounding semantics are not fully established. Assuming
empty reserves would therefore be incorrect. Free manpower additionally depends
on effective recruitment rules and equipment/manpower already assigned to units.

France's land OOB has an unclosed trailing parent. Five independently complete
production children are recovered with original hashes and diagnostics; recovery
does not prove that the malformed source contains every intended statement.
See [starting armies](hoi4-starting-armies.md) for the exact supported semantics.

## Effective economy is more than national modifiers

France's selected national factory-output subtotal is -0.10: its inefficient
economy contributes -0.20 and export focus contributes +0.10. This subtotal still
needs applicable stability, power, equipment/MIO and resource effects before it
becomes a production rate. Likewise, its 35 literal civilian factories are not
35 available construction factories.

The Eiffel Tower contributes +0.05 stability under the selected DLC/controller
conditions. Adding it to the history value alone is incomplete: national spirits,
ruling-party popularity, leader effects and war status can also matter.
Consumer-goods expected fractions add, while consumer-goods factors multiply;
they are preserved separately rather than merged into one national bonus.

See [equipment economics](hoi4-equipment-resolution.md),
[national modifiers](hoi4-modifier-resolution.md), and
[construction/economy arithmetic](../games/hoi4/planning/construction-economy.md)
for sources, APIs and limitations.

## Next implementation checkpoints

1. Assemble an immutable campaign state with a required-input report for actual
   reserves/free manpower, effective state slots and factory pools, initial
   production cohorts, designed equipment costs, power and resource availability.
   Keep unsupported inputs explicit; an absent input is not zero.
2. Connect the tested components through one hourly replay. Reconcile issued
   equipment and reserves, avoid double allocation of factories/resources, and
   check deadlines exactly at their boundary. Apply supplied dated research,
   focus and law changes using runtime hooks rather than history-only semantics.
3. Use replay to validate France and then the other majors. Compare against an
   actual target-version start when installed data becomes available; meanwhile,
   retain public-source disagreement and patch uncertainty in reports.
4. Add the planning search over that same state and replay contract. The objective
   is final usable civilian construction capacity subject to reserve-equipment
   and fully equipped, trained division deadlines. There is no secondary spending
   objective. Nonlinear efficiency needs a faithful formulation or explicitly
   approved approximation before claiming solver optimality.

Research, focuses and laws are supplied dated plans for the first optimizer;
automatically choosing them is outside the agreed first scope. Concrete run
dates, quantities and division templates are query inputs, not missing source
data. The [HoI4simulator review](hoi4-simulator-review.md) records reusable loader
and replay design ideas without adopting its hard-coded gameplay assumptions.

[source]: https://github.com/BanderaModding/vanilla-fin-hoi4/tree/e249d22284449ece5416b41e68c4d73f2b79e3cc
