# Construction and economy arithmetic

The helpers in `construction.py` and `economy.py` implement an explicit hourly
integration of documented rules. They accept supplied effective inputs and
return inspectable breakdowns. They do not derive national modifiers, occupied
factory availability, trade flows, damage, coal demand or event effects.

## Evidence and profile inputs

The [Construction wiki revision 102988][construction] and the [pinned public
defines mirror][defines] document a limit of 15 civilian factories per project.
The wiki documents construction costs of 10,800 IC for a civilian factory,
7,200 for a military factory and 6,000 for infrastructure. For buildings affected
by infrastructure, the documented default multiplier is `1 + 0.2 × level`.
Those are source observations, not automatically selected target-patch defaults.

A separate [versioned installed-data comparison][installed-comparison] explicitly
compares 1.19.3 with 1.19.4.1 and reports no intervening production/building
define changes. It corroborates coal-era base factory speeds and energy
constants. Its infrastructure resource-bonus correction (`0.15`) concerns
resource extraction, not the construction-speed multiplier. This is useful
supplementary evidence; it does not establish complete source identity or
resolve engine completion timing and overflow.

`ConstructionProfile` requires the per-project civilian limit and infrastructure
coefficient. Each `ConstructionProject` explicitly supplies its IC cost,
current progress and infrastructure applicability. `ConstructionAllocation`
supplies the number of civilians and their effective IC per factory per day.
This effective output must already incorporate power and the applicable dated
national, state and building-type modifiers, **excluding infrastructure**, which
the helper applies once. This avoids silently double-counting power or speed.

The caller resolves scheduled laws, focuses, research and other supplied effects
at an hourly boundary, then provides that hour's effective values. The helpers
do not infer the effects or legality of a supplied decision.

## Construction replay and capacity

`advance_construction_hour(states, projects, allocations,
available_civilian_factories=..., profile=..., overflow_policy=...)` computes all
project output from the starting state:

```text
hourly project IC = allocated civilians × effective daily IC
                    × infrastructure multiplier / 24
```

State records contain effective shared-slot capacity, existing civilian and
military factories, other occupied shared slots, infrastructure level and its
maximum level. Pending projects reserve their future slots. Unknown references,
duplicate allocations, over-allocation, more workers than the supplied project
limit, and projects exceeding those capacities fail validation. The supplied
available civilian pool is independent of the counts in individual states so
the caller can account for consumer goods, imports, exports and unavailable
factories explicitly.

Completions update the returned ending state and remove the completed project.
New factories and infrastructure therefore contribute starting with the next
hour. This is an hourly numerical convention, not a verified claim about the
game's internal ordering. Recompute consumer goods and power from the ending
state before choosing the next hour's allocations: adding a civilian factory
does not necessarily add one full available construction factory after those
rules.

Fractional progress is retained. Exact completion overflow remains unresolved:
the source review found no authoritative explanation of its transfer or loss,
and additional web searches were rate-limited. The `overflow_policy` argument
is required, with no default:

- `discard`: report the excess as discarded IC.
- `retain_for_caller`: report excess separately for each completed project;
  the caller must route it explicitly. It is **not** automatically applied to
  another project's progress or banked as interchangeable national IC.

The returned `ConstructionHour` records produced and applied IC, completions,
retained/discarded excess and the number of civilians allocated. This permits
checking that produced IC equals applied IC plus completion overflow. Projects
currently cover civilian factories, military factories and infrastructure,
one building level per project. Repairs, conversion, demolition and other
buildings need their own explicit transition rules.

## Consumer goods

The publisher's [July 19, 2023 developer diary][consumer-goods] documents the
two-step calculation and rounding down:

```text
expected fraction = sum(expected-fraction terms)
factor multiplier = product(1 + each individual factor modifier)
raw fraction = expected fraction × factor multiplier
effective fraction = max(raw fraction, supplied minimum fraction)
percentage requirement = floor(effective fraction × counted factory pool)
requirement = max(percentage requirement, supplied absolute minimum)
allocated = min(requirement, supplied usable civilian factory pool)
construction factories = usable civilian pool − allocated
```

Factor modifiers remain separate and multiply individually; they are not
summed. The pinned defines mirror contains minimum-fraction `0.1` and
minimum-factories `1`, but their full target-version interaction has not been
verified. Both floors must therefore be supplied. The code applies the absolute
floor after flooring the percentage requirement and records any unmet
requirement when the civilian pool is too small. Callers can select an absolute
floor of zero when that is the explicitly selected profile.

The counted factory pool and usable civilian pool are separate inputs. The
helper does not silently decide how occupied, damaged, traded or subject
factories enter either pool. Simple decimal rational arithmetic protects the
integer rounding boundary: `0.29 × 100` yields 29 factories. This arithmetic is
only used for the finite consumer-goods expression, not nonlinear hourly
production-efficiency recurrence.

## Coal-era power

The [June 2025 Thermodynamics diary][thermodynamics] documents linear
interpolation between unpowered and powered factory base output. The
[November 19 launch-eve diary][energy-launch] says that an energy shortage also
scales the relevant sum of modifiers when that sum is positive. Negative or
zero sums do not receive that additional scaling. The [1.17.2 patch notes][energy-patch]
remove the penalty when demand is zero.

`powered_output(PowerInputs(...))` therefore reports:

```text
power fraction = 1 if demand is zero, otherwise min(1, supply / demand)
base output = unpowered output + power fraction × (powered − unpowered output)
modifier sum = sum(relevant supplied modifier terms)
applied modifiers = modifier sum × power fraction, if modifier sum > 0
                    modifier sum, otherwise
effective output = base output × (1 + applied modifiers)
```

Supply, demand, unpowered/powered base IC and modifier terms are all explicit.
The mirror/wiki describe civilian output of 4–5 IC/day and military output of
3.5–4.5; an earlier publisher example instead used military output of 4–4.5.
No source value is selected silently. The helper excludes proposed power-plant
rules from the later beta and does not invent a current coal-demand equation.
See the [broader source review](../../../docs/hoi4/hoi4-rules-review.md) for
version provenance and unresolved interactions.

[construction]: https://hoi4.paradoxwikis.com/index.php?title=Construction&oldid=102988
[defines]: https://github.com/BanderaModding/vanilla-fin-hoi4/blob/e249d22284449ece5416b41e68c4d73f2b79e3cc/common/defines/00_defines.lua
[consumer-goods]: https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/5124584051966124338
[thermodynamics]: https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/1803527891506227
[energy-launch]: https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/1816849002007641
[energy-patch]: https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/1818118366172856
[installed-comparison]: https://github.com/klimPaskov/Agentic-HOI4-Modding/blob/daf409fcba6c3f7c4bf68109d453f02874a71892/hoi4_wiki/defines_additions.md
