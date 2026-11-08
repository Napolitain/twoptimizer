# HoI4 starting-scenario readiness

The requested target is the latest stable game with all gameplay DLC. The public
snapshot provides substantial source material for France and seven other major
countries, but it does not yet establish a runnable starting scenario for that
target. This report separates source availability from interpretation and from
scenario inputs. See [rules review](hoi4-rules-review.md) for version evidence and
[ingestion](hoi4-source-ingestion.md) for source preservation.

## What the snapshot establishes

The pinned public source is
[`BanderaModding/vanilla-fin-hoi4` at `e249d22`][source]. It contains country
histories, state histories, unit definitions, equipment definitions, OOB files,
technology, national ideas, focuses, designer modules, industrial organizations
and initialization scripts. The checked-in reference import exposes selected
declarations from this material; it does not execute the source scripts.

There are 308 direct equipment definitions, 34 `duplicate_archetypes`
declarations and 157 unit definitions. A source dependency audit finds no
duplicate identifiers or cycles in these declared relationships. All unit
references in the 128 candidate division templates resolve. The 128 includes
alternative DLC branches and a non-starting Italian fragmentation OOB; it is
not the number of simultaneously available starting templates.

After indexing the duplicate-archetype declarations, two production equipment
names are absent from the direct definitions:
`small_plane_cas_airframe_1` and
`cv_small_plane_naval_bomber_airframe_1`. Both correspond to generated-type
candidates. This is unimplemented generation, not evidence that the underlying
source is unavailable. Prior to indexing those declarations, 60 archetype
references appeared missing for the same structural reason.

The country histories identify these land OOB candidates when their relevant
DLC conditions are enabled. Air and naval OOBs are selected separately.

| Country | Land OOB candidate | Declared templates | Specific starting-data concern |
| --- | --- | ---: | --- |
| France | `FRA_1936_nsb` | 8 | Trailing production parent is unclosed; five complete production children can be recovered with diagnostics. |
| United Kingdom | `ENG_1936_nsb_LaR` | 6 | Both tank-designer and intelligence DLC conditions affect land selection. |
| United States | `USA_1936` | 5 | Uses the literal `oob` field; air/naval choices and country modifiers remain separate. |
| Germany | `GER_1936_nsb` | 5 | Country setup includes 176 top-level variable assignments and four dynamic-modifier assignments. |
| Italy | `ITA_1936_nsb` | 14 | Country setup also changes state scopes; the fragmentation OOB must not be combined with the starting OOB. |
| Japan | `JAP_1936_nsb` | 8 | Country setup includes designer variants, state scopes and six top-level dynamic-modifier assignments. |
| Soviet Union | `SOV_1936_nsb` | 7 | Setup includes scripted loops, an event and dynamic modifiers; literal variables alone do not resolve their effects. |
| China | `CHI_1936_sea` | 4 | `No Compromise, No Surrender` selects a different OOB; country history also changes state scopes. |

These are source inspection findings, not a claim that all startup scripts have
run or every target-release DLC is represented in the snapshot. The source
bookmark declares `1936.1.1.12`, which is also relevant to hourly deadlines.

## Inputs required for a runnable starting state

| Input | Current evidence | Remaining work or uncertainty |
| --- | --- | --- |
| Exact game build and DLC set | Target version is recorded; the mirror revision is pinned. | Mirror patch identity and vanilla fidelity are unverified. Its August revision predates the selected November hotfix. An all-DLC policy does not repair missing release changes. |
| Selected history and startup scope | Country/state declarations, dated blocks and conditions are retained in source. | Evaluate the requested start time and known DLC predicates; preserve unknown predicates as blockers. Apply scoped effects and initialization hooks in documented order. |
| Territory, buildings and resources | 1,081 state files were examined; base ownership, buildings, resources and state categories were imported. | Resolve country-script state changes, cores, controller/occupation, damage, usable building slots, deposits, resource rights and relevant state modifiers. Literal factory totals are not available construction capacity. |
| Existing military and stockpiles | OOB source contains deployments, templates, starting equipment/experience factors and forced variants. | Import and resolve existing divisions, their issued equipment and deficits, reserve stockpiles, naval/air commitments, deployment queues, and free versus fielded manpower. Imported templates alone do not establish any of these totals. |
| Starting production | Source identifies requested factories, progress, efficiency, equipment types, named variants and industrial organizations. | Select OOB branches, resolve variants/MIO assignments and exact initial efficiency/progress semantics. France recovery preserves five complete children but does not prove its truncated tail is complete. |
| Equipment and designer variants | Direct costs/resources, archetype/parent references and variant/module source files exist. | Resolve documented equipment defaults, generated archetypes/types, module slots, module costs/resources, upgrades, country variants and eligibility. A bare chassis cost is not a complete tank design cost. |
| Division requirements | Template regiment/support entries and unit `need`, manpower and training fields exist. | Resolve duplicate/conditional template definitions, equipment substitutions and allowed variants. Apply documented requirement aggregation and training modifiers; distinguish fully issued equipment from reserve targets. |
| Technologies and research | Starting `set_technology` blocks and `common/technologies` exist. | Select starting branches and import unlocks, production/efficiency/construction bonuses, research costs, prerequisites and modifiers. Future research must be a supplied schedule or part of the decision model. |
| Laws, national ideas and modifiers | Country `add_ideas`, law definitions, national ideas, static/dynamic modifiers and variables exist. | Resolve defaults and starting laws, national spirits, stability/war support, modifier scopes and stacking. Import conditions, costs and effects for selectable changes. |
| Focuses, events and decisions | Focus trees and startup/on-action scripts exist. | Resolve the selected focus tree, grouped prerequisites, availability, completion/bypass effects and any reachable scripted effects/events. Future choices need explicit action semantics. |
| Trade, power and other commitments | Deposits, trade laws and selected defines are available as evidence. | Establish available trading partners, exports/imports, civilian-factory commitments, access/convoys, power demand and shortage behavior. Define any wartime losses, captures, lend-lease or other external changes within the requested horizon. |
| Hourly transition rules | The hourly calendar and sourced rule observations are separate modules/artifacts. | Validate update order, production efficiency, resource allocation, construction completion, rounding, training and stockpile issuance against the target. Parsing declarations does not supply engine behavior. |
| Optimization query | Equipment/division deadline request structures can express targets. | Each run needs concrete quantities, dates, selected templates and the intended trained level; objective measures and permitted decisions must be defined. Missing query inputs are different from missing game data. |

The source paths most relevant to closing these gaps are `history/countries`,
`history/states`, `history/units`, `common/bookmarks`, `common/technologies`,
`common/ideas`, `common/modifiers`, `common/dynamic_modifiers`,
`common/national_focus`, `common/on_actions`, `common/scripted_effects`,
`common/units/equipment/modules` and
`common/military_industrial_organization/organizations`. Their presence does not
mean the current reference importer handles their semantics.

For France specifically, source history adds `FRA_full_employment`,
`FRA_inefficient_economy_2`, `limited_conscription` and other national ideas.
The inefficient-economy definition contains a factory-output penalty. Its
country history also creates named equipment variants, while starting production
names variants and industrial organizations. Ignoring these connections would
produce a runnable calculation with incorrect starting inputs.

## Inheritance and templates

The dependency validator keeps `parent`, `archetype` and
`duplicates_archetype` as distinct edges. `trace_equipment_field` reports each
sourced candidate declaration and its path without choosing an effective value.
For example, a child's predecessor and its archetype can both declare a cost;
the existence of both references does not establish an override order.

Some structural behavior is documented directly in the source. Equipment module
slots can explicitly use `inherit`, and module-count limits describe matching
override conditions. The `x_tank_chassis.txt` and `x_plane_airframes.txt` comments
describe duplicate archetypes, excluded attributes and per-derived-type
transformations. These provide concrete implementation opportunities with
source-backed tests. A generic recursive dictionary merge would lose the
different behaviors.

For simple infantry/support templates, all regiment and support-unit references
can already be followed to direct equipment-need declarations. This makes
source-factual requirement summaries feasible. It does not establish equipment
substitution, unlocked technology, effective cost, initial army shortages or
training progress. Designer equipment requires the additional variant/module
resolution above.

## Next implementation checkpoints

1. Validate a restricted starting-history interpreter: explicit date/DLC inputs,
   supported condition/effect lists, provenance on every assignment, and errors
   for relevant unresolved branches. Do not treat an unknown condition as false.
2. Expand the reachable data definitions for technologies, laws/ideas, dynamic
   modifiers, designer modules and industrial organizations. Keep source
   dependencies and unresolved references visible to the shared inspector.
3. Implement documented equipment generation/inheritance separately from
   template aggregation, with tests for alternative sources and collisions.
4. Resolve selected starting OOBs, production, existing army requirements and
   stockpiles into an immutable scenario. Maintain explicit diagnostics for
   damaged source and target-build uncertainty.
5. Validate that scenario and hourly transitions before claiming an optimized
   France plan. Repeat the same importer and checks for the seven other majors.

The external reference simulator is useful for structural comparisons but does
not close these gaps. Its installed-data path does reconstruct fielded divisions
from OOB templates and equipment factors, using incomplete hardcoded demand
tables. Its curated example uses daily steps, a different infrastructure cost
and simplified efficiency growth. The [deeper simulator review](hoi4-simulator-review.md)
records useful design ideas and the mappings that require replacement.

[source]: https://github.com/BanderaModding/vanilla-fin-hoi4/tree/e249d22284449ece5416b41e68c4d73f2b79e3cc
