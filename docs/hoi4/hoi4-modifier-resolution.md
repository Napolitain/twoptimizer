# Initial HoI4 economic modifiers

`games.hoi4.data_pipeline.modifier_resolution` resolves the initial country
history selected by a start date and explicit DLC context. It indexes ideas,
technologies and dynamic modifiers from a caller-selected source checkout.
`load_modifier_catalog(root)` returns an immutable catalog with `input_sources`
fingerprints. `resolve_country_modifiers(document, context, catalog, tag="FRA")`
returns source-backed contributions, known subtotals and unresolved effects.

This is a source-resolution layer, not a complete campaign simulator. The target
remains latest stable with all gameplay DLC; the pinned public mirror's exact
patch remains unverified. Its numerical observations are not validated current
engine defaults. The report always leaves `effective_country_economy_resolved`
and `scenario_ready` false.

## Implemented source semantics

- Select dated and DLC branches conservatively using the shared selector.
- Discover eligible `default = yes` laws. An ambiguous or unknown default is
  reported; no ordering tie-break is invented. An explicit law replaces the
  active law in that category. The pinned idea-tag file supplies one government
  slot for each of mobilization, trade and economy.
- Apply ordered `add_ideas` and `remove_ideas`, including list and scalar forms.
  Repeatedly adding the same idea does not duplicate its modifiers. Explicit
  additions bypass `allowed`; this matters because France's starting spirits
  deliberately have `always = no` in their selection eligibility.
- Keep `do_effect` distinct from selection eligibility. Known false disables
  the contribution; an unknown condition is a blocker for the affected fields.
  Guards support explicit DLC/date context, booleans and country-tag checks.
- Apply country modifiers from researched technologies. Zero-level technology
  declarations remove previously selected technology; unsupported levels remain
  unresolved. Research paths, AI weights and availability metadata do not add
  economic bonuses.
- Do not run idea `on_add`/`on_remove` or technology `on_research_complete`
  for history initialization. The cited modding documentation explicitly
  distinguishes this from changes after the game starts.
- Resolve literal initial variable assignments, copied values and arithmetic
  used by dynamic modifiers. The [variable documentation][variables] establishes
  zero for a genuinely unset local variable; contributions mark this as
  `value_origin = unset_variable_default`. Unknown evaluated expressions or
  possible writes in unresolved branches stay unknown. Unused unresolved
  variables do not block unrelated economic fields. Dynamic values describe
  the selected initial state, not future daily updates.
- Resolve explicitly hired advisor `idea_token` identifiers through recruited
  characters and their national traits. Recruiting a character alone does not
  hire its advisor role. [Character][characters] and [effect][effects]
  documentation establish the advisor-as-idea lookup and law-slot replacement.

The implementation handles national construction, output, efficiency,
consumer-goods, trade, resources, energy and recruitment modifier fields.
The precise field allowlist is `ECONOMIC_MODIFIERS`, plus construction-speed
and resource-specific fields. It also preserves stability and war-support
contributions for their owning mechanics. Immediate equipment cost bonuses
expand their source equipment groups into exact selectors, including nested
groups. They remain scoped relative cost factors, to be matched against the
equipment ID or archetype by the equipment resolver. Deferred bonuses and
unrecognized equipment effects remain blockers. Unrelated portraits, research
cost metadata and combat statistics do not block this limited calculation.

The [modifier documentation][modifiers] specifies that the same numeric modifier
generally adds across sources. Consumer goods has a distinct exception:
`consumer_goods_expected_value` adds, while each `consumer_goods_factor` applies
as a separate multiplier `1 + factor`. Both the [publisher diary][consumer]
and the wiki document that distinction. Reports therefore keep
`additive_modifiers` and `multiplicative_modifiers` separate. They do not apply
the engine's factory-count rounding or minimums at this stage.

The known subtotals are **not complete values when blockers remain**.
`blocked_fields` identifies affected known fields where possible; a missing
definition or unresolved history branch can have an unknown wider impact.
The report's completion flag applies only to selected ideas, technologies and
dynamic modifiers within this module's supported scope.

## France and other major-country observations

On the pinned public snapshot, selecting January 1, 1936 at 12:00 with the
catalogued gameplay DLC resolves France's default civilian economy and export
focus alongside its explicitly selected limited conscription and spirits:

| Selected contribution | Source value |
| --- | ---: |
| Civilian economy expected consumer goods | 0.35 |
| Civilian economy civilian/military construction modifiers | -0.30 each |
| Export focus national construction modifier | +0.10 |
| Export focus factory output | +0.10 |
| Inefficient economy factory output | -0.20 |
| Limited conscription recruitable fraction | +0.025 |
| Victors of the Great War recruitable fraction | -0.003 |
| Full employment recruitable-population factor | -0.25 |

Thus the selected factory-output subtotal is -0.10; the additive recruitable
fraction subtotal is 0.022, with the separate -0.25 factor retained. A recruitable
fraction does not establish available free manpower. The resolver does not
merge the construction modifiers: the construction mechanic must apply the
national and building-specific contributions in their appropriate scopes.

The eight-major-country smoke check resolves the supported selected modifiers
for all eight countries without blockers. This includes German MEFO variables,
Italian industry modifiers, six Japanese scoped equipment cost terms and the
Soviet Yagoda advisor's -0.05 stability trait. China's two unset corruption
variables resolve to the documented zero default; their later national-focus
writes are not pulled into the starting snapshot. These are source-resolution
results, not validation against the game or a complete country-economy claim.

Three public idea files have an unclosed outer `ideas` block. When every nested
category is independently balanced, the loader recovers those complete children
while preserving the original full-file hash and parse diagnostic. It never
inserts a closing brace or accepts an incomplete child as a definition. This
recovers the complete Soviet idea definitions without disguising source damage.

## Remaining boundaries

State and landmark effects, unhired or leader character roles, stability,
war support, occupation,
trade contracts and arbitrary scripted effects require their own resolution.
For example, France's Eiffel Tower contributes stability through a landmark
building, while its history already subtracts that expected bonus from its
explicit starting stability. Idea-only stability would therefore be incomplete.
Unsupported equipment bonuses, conditional scopes and unresolved dynamic
removal conditions remain explicit blockers. Known government predicates can
disprove removal conditions; tooltip-only dynamic modifiers have no numeric
economic contribution. Scheduled law/research changes require a runtime
executor that applies the relevant hooks; reusing history initialization would
incorrectly suppress them.

Unknown evaluated variables, dynamic update ordering, incomplete source patches
and unhandled scoped effects must not be replaced with guessed zero values.

## Stability and war-support evaluator

`resolve_support_profile(catalog)` extracts economic endpoint tables from
`common/modifiers/00_static_modifiers.txt` with file hashes and line references.
The five keys under `tables` are `stability_good_modifier`,
`stability_bad_modifier`, `war_support_good_modifier`,
`war_support_bad_modifier` and `war_support_during_war`. Missing or nonliteral
tables make `source_values_complete` false.

`games.hoi4.planning.support.support_effects` consumes those coefficients and
explicit current stability, war support and war status. The [Government page][government]
documents flooring stability to whole percentage points before its piecewise
linear effects around 50%. It also documents the separate linear wartime
stability penalty, strongest at zero war support. The returned wartime term is
not added a second time to the already resolved stability input.

The good/bad war-support endpoint values and neutral 50% point are established,
but the inspected evidence does not explicitly establish their interior
interpolation or rounding. Interior `war_support_modifiers` therefore remains
`None` unless an explicit `war_support_modifier_scale` is supplied. This does
not prevent computing the independently documented stability effects.

Reconstructing effective stability requires all national/leader/landmark
contributions, ruling-party popularity and war effects, followed by clamping.
France's 0.45 history value plus 0.05 Eiffel Tower contribution alone is not its
full effective stability: its national spirits and ruling-party contribution
must also be accounted for.

## Evidence

- [Idea modding, revision 99295][ideas]: regular modifier scope, explicit
  `add_ideas` bypass, `do_effect`, and history hook exclusions.
- [Technology modding, revision 104524][technologies]: national versus unit
  modifier scopes and history research-hook exclusions.
- [Modifiers, revision 102188][modifiers]: aggregation rules and dynamic behavior.
- [Pinned France ideas][france]: economic and manpower values.
- [Pinned economic laws][laws] and [manpower laws][manpower]: defaults and values.
- [Pinned idea slots][slots]: one listed slot per government law category.
- [Pinned landmarks][landmarks]: Eiffel Tower country modifier and DLC guard.
- [Pinned equipment groups][groups]: exact membership, with the adjacent
  `_documentation.md` establishing group nesting and use in `equipment_bonus`.
- [Pinned static modifiers][static]: support endpoint coefficients.

[ideas]: https://hoi4.paradoxwikis.com/index.php?title=Idea_modding&oldid=99295
[technologies]: https://hoi4.paradoxwikis.com/index.php?title=Technology_modding&oldid=104524
[modifiers]: https://hoi4.paradoxwikis.com/index.php?title=Modifiers&oldid=102188
[consumer]: https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/5124584051966124338
[france]: https://github.com/BanderaModding/vanilla-fin-hoi4/blob/e249d22284449ece5416b41e68c4d73f2b79e3cc/common/ideas/france.txt
[laws]: https://github.com/BanderaModding/vanilla-fin-hoi4/blob/e249d22284449ece5416b41e68c4d73f2b79e3cc/common/ideas/_economic.txt
[manpower]: https://github.com/BanderaModding/vanilla-fin-hoi4/blob/e249d22284449ece5416b41e68c4d73f2b79e3cc/common/ideas/_manpower.txt
[slots]: https://github.com/BanderaModding/vanilla-fin-hoi4/blob/e249d22284449ece5416b41e68c4d73f2b79e3cc/common/idea_tags/00_idea.txt
[landmarks]: https://github.com/BanderaModding/vanilla-fin-hoi4/blob/e249d22284449ece5416b41e68c4d73f2b79e3cc/common/buildings/01_landmark_buildings.txt
[variables]: https://hoi4.paradoxwikis.com/index.php?title=Data_structures&oldid=103616
[characters]: https://hoi4.paradoxwikis.com/index.php?title=Character_modding&oldid=99479
[effects]: https://hoi4.paradoxwikis.com/index.php?title=Effect&oldid=104907
[government]: https://hoi4.paradoxwikis.com/index.php?title=Government&oldid=99350
[groups]: https://github.com/BanderaModding/vanilla-fin-hoi4/blob/e249d22284449ece5416b41e68c4d73f2b79e3cc/common/equipment_groups/mio_equipment_groups.txt
[static]: https://github.com/BanderaModding/vanilla-fin-hoi4/blob/e249d22284449ece5416b41e68c4d73f2b79e3cc/common/modifiers/00_static_modifiers.txt
