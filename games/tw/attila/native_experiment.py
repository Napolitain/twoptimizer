"""Opt-in native multiplication experiment over an unchanged Attila reference.

The frozen wrapper changes only the compact CP-SAT encoding. It preserves the
normal competition solver's result validation, hints, cancellation and timing;
the source model and its default compact plan are never mutated. Experimental
native products also permit the compact encoding for quadratic objectives whose
production policy currently prefers the expanded Boolean formulation.
"""

from dataclasses import dataclass, replace

from games.tw.attila.compact import CompactIncome
from games.tw.competition import BinaryModel


@dataclass(frozen=True, slots=True)
class NativeProductPlan:
    original: CompactIncome

    def solve(self, reference, seconds, seed, workers, **options):
        return self.original.solve(
            reference, seconds, seed, workers, native_products=True, **options
        )


def with_native_products(model: BinaryModel) -> BinaryModel:
    """Return a model selecting native products without replacing any economics."""
    plan = model.cp_sat_plan
    if isinstance(plan, NativeProductPlan):
        return model
    if not isinstance(plan, CompactIncome):
        raise ValueError("Native Attila products require a compiled compact-income reference")
    return replace(model, cp_sat_plan=NativeProductPlan(plan))
