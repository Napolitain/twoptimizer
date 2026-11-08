# Hourly planning time

`CampaignDate` represents HoI4 dates with integer hours and a 365-day calendar.
It is immutable, rejects invalid dates (including February 29), and does not use
timezones, local clocks or floating-point timestamps. Source dates such as
`1936.1.1` mean midnight; canonical serialization is `1936.01.01.00`.

The calendar is a sourced game fact. The HoI4 wiki's
[Event modding revision 102070](https://hoi4.paradoxwikis.com/index.php?title=Event_modding&oldid=102070)
states: “For the calculation of the amount of days to be correct, leap days must
be ignored as the game doesn’t contain them.” The passage is preserved in a
[pinned public mirror](https://github.com/CooderAtom/hoi4-zh-wiki/blob/9f15dbe333f50742f0afd075bcb5a69c7c2ff39c/site/Event_modding.html),
fetched September 10, 2026. It establishes the calendar; it does not establish
the ordering or frequency of economic updates.

`HourlyHorizon(start, deadline)` represents the half-open work interval
`[start, deadline)`. For example, 08:00 through 10:00 contains two one-hour
intervals. Offset 2 identifies the 10:00 boundary for checking a deadline, but
does not create another hour of production. Equal start/deadline dates contain
zero work intervals and allow checking initial conditions. Horizon serialization
explicitly names `hoi4_no_leap`, preventing silent interpretation as a Gregorian
calendar.

These helpers do not choose production formulas, event ordering, construction
completion rules, rates, deadlines or starting scenarios. The old experimental
`models.game_date.GameDate` remains unchanged for legacy examples; new hourly
plans must use the explicit calendar type.

```python
from games.hoi4.planning import CampaignDate, HourlyHorizon

horizon = HourlyHorizon(
    CampaignDate.parse("1936.2.28.23"),
    CampaignDate.parse("1936.3.1.1"),
)
assert horizon.hours == 2
assert list(horizon.offsets()) == [0, 1]
assert str(horizon.date_at(horizon.hours)) == "1936.03.01.01"
```

## Planning input contract

`contracts.PlanningContract` is a versioned, immutable record of a player's
targets and supplied schedule. `from_json` and `from_dict` reject missing or
unknown fields, duplicate JSON fields, negative counts, booleans masquerading
as integers, duplicate target dates for the same entity, undeclared division
template references, and dates outside the horizon. The initial and final
boundaries are valid target or event times. `to_json` produces deterministic
JSON while preserving the order of input arrays.

The explicit ruleset target is `1.19.4`, checksum `0bdb`, with `all_gameplay`
DLC. This identifies the selected target; it does not certify that an imported
dataset matches that target. Country, unit, equipment, decision and external
template IDs still require resolution against verified game data.

Equipment targets require an explicit accounting value: `reserve` means an
unissued stockpile; `including_issued` records a target including equipment
issued to units. The user's selected model uses reserve stockpiles in addition
to fully equipped divisions. The structural format can preserve either value;
a model must check which accounting it supports instead of guessing.

Division targets reference declared templates. Each template supplies either
explicit battalion/support placements or an external `source_template_id`,
exclusively. Coordinates must be nonnegative integers and unique within each
of the battalion and support grids. Grid size, unit eligibility, equipment,
manpower and training requirements are not inferred here.

Research and focus decisions require `started` or `completed`; laws require
`enacted`. Dates and phases are supplied facts, not a derived action schedule.
The contract does not pair starts with completions, derive effects or durations,
validate prerequisites, or define the ordering of simultaneous events. It has
no initial economy, production formulas, construction actions or solver result.
Passing validation therefore does not establish feasibility or make the input
an executable campaign scenario.

The following is a **synthetic schema example**, not a France scenario,
recommended target, game-legal template or default deadline. `TST` and the IDs
are placeholders, and every date and quantity is explicitly illustrative:

```json
{
  "schema_version": 1,
  "ruleset": {
    "game_version": "1.19.4",
    "checksum": "0bdb",
    "dlc_profile": "all_gameplay"
  },
  "country_tag": "TST",
  "horizon": {
    "calendar": "hoi4_no_leap",
    "start": "1936.01.01.00",
    "deadline": "1936.01.03.00"
  },
  "division_templates": [
    {
      "template_id": "example_template",
      "battalions": [{"unit_id": "example_unit", "row": 0, "column": 0}],
      "support": []
    }
  ],
  "equipment_targets": [
    {
      "equipment_id": "example_equipment",
      "quantity": 100,
      "deadline": "1936.01.03.00",
      "accounting": "reserve"
    }
  ],
  "division_targets": [
    {"template_id": "example_template", "count": 1, "deadline": "1936.01.03.00"}
  ],
  "decisions": [
    {
      "at": "1936.01.01.00",
      "kind": "research",
      "identifier": "example_technology",
      "phase": "started"
    }
  ]
}
```

Parse it with `PlanningContract.from_json(text)` from
`games.hoi4.planning.contracts`. All top-level fields are required in serialized
inputs; empty arrays explicitly represent no entries. An empty target set is
structurally valid and still makes no feasibility claim.

## Provisional hourly mechanics

`mechanics.py` contains pure arithmetic building blocks for the approved
hourly approximation. These helpers are not a campaign simulator or solver.
They take explicit effective inputs; they do not obtain rules or initial state
from the planning contract or public reference snapshots.

`advance_production_hour(EfficiencyCohort, ProductionProfile)` advances one
active hour. The profile requires effective IC per factory per day, efficiency
cap, daily growth coefficient and gain multiplier. Effective IC must already
account for resources, power and other modifiers. The documented daily curve
uses coefficient `0.001`; see the [rules evidence review](../../../../docs/hoi4-rules-review.md).
The helper has no implicit coefficient or starting efficiency.

Production uses the starting efficiency for the hour, retains fractional IC in
the cohort, then applies forward Euler growth at the ending boundary:

```text
output IC = factories × effective IC/factory/day × efficiency / 24
next efficiency = min(cap, efficiency + coefficient × cap² / efficiency × gain / 24)
```

This is a numerical integration convention, not a verified engine tick order.
Finite float64 arithmetic keeps the nonlinear recurrence practical over tens
of thousands of hours. No rounding to whole equipment occurs, so small hourly
amounts are conserved in carried IC. Efficiency must be positive and no greater
than the supplied cap. Idle lines, cap reductions, equipment switching,
retention, discrete equipment delivery and IC allocation need explicit handling
by the eventual model.

`advance_recruitment_hour(RecruitmentProgress, fully_equipped=...,
manpower_available=...)` credits at most one hour, up to an explicit required
duration, only when both caller-supplied gates are true. An ineligible hour adds
no progress. It does not decide manpower/equipment allocation or whether losses
should reset past progress. `ready_at_boundary` checks completed training and
current equipment/manpower gates without advancing another hour. Iterate only
the horizon's work offsets, then check its final boundary; a division one hour
short at the deadline remains unready.

`construction.py` and `economy.py` add simultaneous construction, completion
records, slot reservations, consumer-goods breakdowns and supplied power/output
accounting. See [construction and economy arithmetic](construction-economy.md)
for the inputs, source evidence and explicit completion-overflow policy.
