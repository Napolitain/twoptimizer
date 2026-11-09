"""Conservative conversion of floating-point solver certificates."""

from math import ceil, isfinite


def integer_upper_bound(value: float) -> int | None:
    """Round a genuine bound outward only inside the exact double-integer range.

    Callers must establish that the solver actually emitted a bound: UNKNOWN
    response defaults are not certificates. Outside this range, retain the exact
    Python-integer domain bound rather than trusting a possibly rounded double.
    """
    return ceil(value) if isfinite(value) and abs(value) < 2**53 else None
