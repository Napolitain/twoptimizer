"""Immutable HoI4 dates and exact integer-hour planning intervals.

HoI4 has no leap days. The sourced calendar rule is documented in
``games/hoi4/planning/README.md``. These helpers specify elapsed time and interval
boundaries only; they do not choose economic rates or within-hour update order.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass

HOURS_PER_DAY = 24
DAYS_PER_YEAR = 365
MONTH_LENGTHS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
CALENDAR_ID = "hoi4_no_leap"
_SOURCE_DATE = re.compile(r"([0-9]+)\.([0-9]{1,2})\.([0-9]{1,2})(?:\.([0-9]{1,2}))?")


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be a whole number")
    return value


@dataclass(frozen=True, slots=True, order=True)
class CampaignDate:
    """A timezone-free date in HoI4's 365-day calendar, at whole-hour precision."""

    year: int
    month: int
    day: int
    hour: int = 0

    def __post_init__(self) -> None:
        for name in ("year", "month", "day", "hour"):
            _integer(getattr(self, name), name.capitalize())
        if self.year < 1:
            raise ValueError("Year must be positive")
        if not 1 <= self.month <= len(MONTH_LENGTHS):
            raise ValueError("Month must be between 1 and 12")
        if not 1 <= self.day <= MONTH_LENGTHS[self.month - 1]:
            raise ValueError("Day is invalid in HoI4's no-leap calendar")
        if not 0 <= self.hour < HOURS_PER_DAY:
            raise ValueError("Hour must be between 0 and 23")

    @classmethod
    def parse(cls, text: str) -> CampaignDate:
        """Read a source date ``YYYY.M.D`` or ``YYYY.M.D.H``; omitted hour is zero."""
        match = _SOURCE_DATE.fullmatch(text) if isinstance(text, str) else None
        if match is None:
            raise ValueError("Use a HoI4 date in YYYY.M.D or YYYY.M.D.H form")
        year, month, day, hour = match.groups()
        return cls(int(year), int(month), int(day), 0 if hour is None else int(hour))

    def to_dict(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in ("year", "month", "day", "hour")}

    @classmethod
    def from_dict(cls, values: Mapping[str, object]) -> CampaignDate:
        if not isinstance(values, Mapping):
            raise ValueError("A campaign date must be an object")
        required = {"year", "month", "day"}
        if not required <= values.keys() or values.keys() - required - {"hour"}:
            raise ValueError("A campaign date needs year, month and day, with an optional hour")
        return cls(
            _integer(values["year"], "Year"),
            _integer(values["month"], "Month"),
            _integer(values["day"], "Day"),
            _integer(values.get("hour", 0), "Hour"),
        )

    def to_hour_index(self) -> int:
        """Hours since ``0001.01.01.00``, using no floating-point arithmetic."""
        days = (self.year - 1) * DAYS_PER_YEAR + sum(MONTH_LENGTHS[: self.month - 1]) + self.day - 1
        return days * HOURS_PER_DAY + self.hour

    @classmethod
    def from_hour_index(cls, index: int) -> CampaignDate:
        index = _integer(index, "Hour index")
        if index < 0:
            raise ValueError("Hour index cannot precede 0001.01.01.00")
        days, hour = divmod(index, HOURS_PER_DAY)
        year_offset, day_offset = divmod(days, DAYS_PER_YEAR)
        month = 1
        for days_in_month in MONTH_LENGTHS:
            if day_offset < days_in_month:
                break
            day_offset -= days_in_month
            month += 1
        return cls(year_offset + 1, month, day_offset + 1, hour)

    def add_hours(self, hours: int) -> CampaignDate:
        return self.from_hour_index(self.to_hour_index() + _integer(hours, "Hours"))

    def hours_until(self, other: CampaignDate) -> int:
        if not isinstance(other, CampaignDate):
            raise ValueError("The other date must use CampaignDate")
        return other.to_hour_index() - self.to_hour_index()

    def __str__(self) -> str:
        return f"{self.year:04d}.{self.month:02d}.{self.day:02d}.{self.hour:02d}"


@dataclass(frozen=True, slots=True)
class HourlyHorizon:
    """Work intervals ``[start, deadline)`` with a separately addressable deadline.

    Offset ``hours`` denotes the deadline boundary, where targets can be checked.
    It is absent from ``offsets()`` and cannot create an extra hour of work.
    A zero-hour horizon permits checking initial conditions without advancing.
    """

    start: CampaignDate
    deadline: CampaignDate

    def __post_init__(self) -> None:
        if not isinstance(self.start, CampaignDate) or not isinstance(self.deadline, CampaignDate):
            raise ValueError("A horizon requires CampaignDate start and deadline")
        if self.deadline < self.start:
            raise ValueError("Deadline cannot precede the start")

    @property
    def hours(self) -> int:
        return self.start.hours_until(self.deadline)

    def offsets(self) -> range:
        """Lazy offsets of each one-hour interval's start; no interval at the deadline."""
        return range(self.hours)

    def date_at(self, offset: int) -> CampaignDate:
        offset = _integer(offset, "Hour offset")
        if not 0 <= offset <= self.hours:
            raise ValueError("Hour offset must be within the start/deadline boundaries")
        return self.start.add_hours(offset)

    def offset_of(self, date: CampaignDate) -> int:
        offset = self.start.hours_until(date)
        if not 0 <= offset <= self.hours:
            raise ValueError("Date must be within the start/deadline boundaries")
        return offset

    def to_dict(self) -> dict[str, str]:
        return {
            "calendar": CALENDAR_ID,
            "start": str(self.start),
            "deadline": str(self.deadline),
        }

    @classmethod
    def from_dict(cls, values: Mapping[str, str]) -> HourlyHorizon:
        if not isinstance(values, Mapping) or set(values) != {"calendar", "start", "deadline"}:
            raise ValueError("A horizon needs calendar, start and deadline")
        if values["calendar"] != CALENDAR_ID:
            raise ValueError(f"Calendar must be {CALENDAR_ID}")
        return cls(CampaignDate.parse(values["start"]), CampaignDate.parse(values["deadline"]))
