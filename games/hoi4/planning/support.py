"""Documented stability interpolation and explicit war-support coefficients.

Government wiki revision mirrored at 9f15dbe333f50742f0afd075bcb5a69c7c2ff39c
documents stability effects using whole percentage points and scaling from 50%.
The caller supplies already resolved current values and source-specific endpoint
modifiers; this module does not infer political, landmark or war state.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal


@dataclass(frozen=True, slots=True)
class SupportEffects:
    stability_used: float
    stability_scale: float
    war_support_scale: float | None
    stability_modifiers: tuple[tuple[str, float], ...]
    war_support_modifiers: tuple[tuple[str, float], ...] | None
    war_stability_modifier: float


def _fraction(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite fraction")
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be between zero and one")
    return value


def _scaled(values: Mapping[str, float], factor: float):
    result = []
    for field, value in values.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError(f"Endpoint modifier {field} must be finite")
        result.append((field, value * factor))
    return tuple(sorted(result))


def support_effects(
    *,
    stability: float,
    war_support: float,
    at_war: bool,
    stability_good: Mapping[str, float],
    stability_bad: Mapping[str, float],
    war_support_good: Mapping[str, float],
    war_support_bad: Mapping[str, float],
    war_stability_penalty_at_zero_support: float,
    war_support_modifier_scale: float | None = None,
) -> SupportEffects:
    """Evaluate endpoint tables without mixing consumer-goods and additive terms.

    ``stability`` is the effective, clamped current fraction including all known
    sources. The returned war-stability term is informational for its separate
    reconstruction step; it is not added to that already-resolved input again.
    Interior good/bad war-support interpolation is not established by the cited
    evidence. Supply an explicit scale or receive an unknown result for that
    subsystem; the documented neutral point and endpoints need no override.
    """
    _fraction(stability, "Stability")
    _fraction(war_support, "War support")
    if type(at_war) is not bool:
        raise ValueError("War status must be an explicit boolean")
    _scaled({"war_stability": war_stability_penalty_at_zero_support}, 1)
    stability_used = float(
        (Decimal(str(stability)) * 100).to_integral_value(rounding=ROUND_FLOOR) / 100
    )
    stability_scale = abs(2 * stability_used - 1)
    war_support_scale = _war_support_scale(war_support, war_support_modifier_scale)
    return SupportEffects(
        stability_used,
        stability_scale,
        war_support_scale,
        _scaled(stability_good if stability_used >= 0.5 else stability_bad, stability_scale),
        _scaled(war_support_good if war_support >= 0.5 else war_support_bad, war_support_scale)
        if war_support_scale is not None
        else None,
        war_stability_penalty_at_zero_support * (1 - war_support) if at_war else 0,
    )


def _war_support_scale(value: float, explicit: float | None) -> float | None:
    if explicit is not None:
        return _fraction(explicit, "War support modifier scale")
    return 0 if value == 0.5 else 1 if value in (0, 1) else None
