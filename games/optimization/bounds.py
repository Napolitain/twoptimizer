"""Results shared by searches that certify bounds and validate complete hints."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BoundSearchResult:
    upper_bound: int | None
    hint_values: dict[int, int] | None
    report: dict[str, object]
