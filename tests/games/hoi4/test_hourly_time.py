"""HoI4 calendar boundaries and work intervals without an extra deadline tick."""

import json
from dataclasses import FrozenInstanceError

import pytest
from hypothesis import given
from hypothesis import strategies as st

from games.hoi4.planning import CampaignDate, HourlyHorizon


def test_no_leap_day_even_in_gregorian_leap_year():
    last_february_hour = CampaignDate(1936, 2, 28, 23)
    assert last_february_hour.add_hours(1) == CampaignDate(1936, 3, 1)
    assert CampaignDate(1936, 1, 1).hours_until(CampaignDate(1937, 1, 1)) == 365 * 24
    assert last_february_hour.hours_until(CampaignDate(1936, 3, 1, 1)) == 2


@pytest.mark.parametrize(
    "values",
    [
        (1936, 2, 29, 0),
        (1937, 2, 29, 0),
        (1936, 4, 31, 0),
        (1936, 1, 0, 0),
        (1936, 0, 1, 0),
        (1936, 13, 1, 0),
        (1936, 1, 1, -1),
        (1936, 1, 1, 24),
        (0, 1, 1, 0),
        (True, 1, 1, 0),
        (1936, 1.0, 1, 0),
        (1936, 1, "1", 0),
        (1936, 1, 1, False),
    ],
)
def test_dates_reject_invalid_calendar_values_and_noninteger_components(values):
    with pytest.raises(ValueError):
        CampaignDate(*values)


def test_month_and_year_rollover_can_be_reversed_without_mutation():
    start = CampaignDate(1936, 12, 31, 23)
    finish = start.add_hours(25)
    assert finish == CampaignDate(1937, 1, 2)
    assert finish.add_hours(-25) == start
    assert finish.hours_until(start) == -25
    assert start == CampaignDate(1936, 12, 31, 23)


@pytest.mark.parametrize("attribute", ["year", "month", "day", "hour"])
def test_campaign_dates_are_immutable(attribute):
    with pytest.raises(FrozenInstanceError):
        setattr(CampaignDate(1936, 1, 1), attribute, 1)


def test_source_dates_and_explicit_calendar_round_trip():
    assert CampaignDate.parse("1936.1.1") == CampaignDate.parse("1936.01.01.00")
    assert str(CampaignDate.parse("1936.1.1.6")) == "1936.01.01.06"
    date = CampaignDate.from_dict({"year": 1936, "month": 1, "day": 1})
    assert CampaignDate.from_dict(json.loads(json.dumps(date.to_dict()))) == date
    horizon = HourlyHorizon(date, date.add_hours(49))
    assert horizon.to_dict() == {
        "calendar": "hoi4_no_leap",
        "start": "1936.01.01.00",
        "deadline": "1936.01.03.01",
    }
    assert HourlyHorizon.from_dict(json.loads(json.dumps(horizon.to_dict()))) == horizon


@pytest.mark.parametrize(
    "text",
    ["1936-01-01", "1936.1.1.0.1", "1936.1.1 01:00", " 1936.1.1", "1936.1.1\n", 1936, None],
)
def test_source_parser_does_not_discard_minutes_or_unknown_syntax(text):
    with pytest.raises(ValueError, match="form"):
        CampaignDate.parse(text)


@pytest.mark.parametrize(
    "values",
    [
        {"year": 1936, "month": 1},
        {"year": 1936, "month": 1, "day": 1, "minute": 30},
        {"year": "1936", "month": 1, "day": 1},
        {"year": 1936, "month": 1, "day": True},
        [1936, 1, 1],
    ],
)
def test_date_serialization_rejects_partial_unknown_or_coerced_values(values):
    with pytest.raises(ValueError):
        CampaignDate.from_dict(values)


@pytest.mark.parametrize("hours", [True, 1.5, "24", None])
def test_hour_arithmetic_rejects_truncation(hours):
    date = CampaignDate(1936, 1, 1)
    with pytest.raises(ValueError, match="whole number"):
        date.add_hours(hours)
    with pytest.raises(ValueError, match="whole number"):
        CampaignDate.from_hour_index(hours)
    with pytest.raises(ValueError, match="whole number"):
        HourlyHorizon(date, date.add_hours(48)).date_at(hours)


def test_hour_epoch_and_large_integers_are_exact():
    epoch = CampaignDate(1, 1, 1)
    assert epoch.to_hour_index() == 0
    assert CampaignDate.from_hour_index(0) == epoch
    assert CampaignDate.from_hour_index(2**80 + 17).to_hour_index() == 2**80 + 17
    with pytest.raises(ValueError, match="precede"):
        epoch.add_hours(-1)


@pytest.mark.parametrize("other", ["1936.1.1", None])
def test_calendar_operations_do_not_coerce_other_date_types(other):
    date = CampaignDate(1936, 1, 1)
    with pytest.raises(ValueError, match="CampaignDate"):
        date.hours_until(other)
    with pytest.raises(ValueError, match="CampaignDate"):
        HourlyHorizon(other, date)


def test_deadline_boundary_does_not_create_an_extra_work_hour():
    start = CampaignDate(1936, 1, 1, 8)
    horizon = HourlyHorizon(start, CampaignDate(1936, 1, 1, 10))
    assert horizon.hours == 2
    assert isinstance(horizon.offsets(), range)
    assert list(horizon.offsets()) == [0, 1]
    assert horizon.date_at(2) == horizon.deadline
    assert horizon.offset_of(horizon.deadline) == 2
    assert 2 not in horizon.offsets()
    assert [horizon.date_at(offset).hour for offset in horizon.offsets()] == [8, 9]


def test_zero_hour_horizon_allows_only_the_initial_boundary():
    date = CampaignDate(1936, 1, 1, 6)
    horizon = HourlyHorizon(date, date)
    assert horizon.hours == 0 and list(horizon.offsets()) == []
    assert horizon.date_at(0) == date and horizon.offset_of(date) == 0
    with pytest.raises(ValueError, match="boundaries"):
        horizon.date_at(1)


def test_horizon_rejects_reversed_or_outside_dates():
    start = CampaignDate(1936, 1, 1, 12)
    with pytest.raises(ValueError, match="precede"):
        HourlyHorizon(start, CampaignDate(1936, 1, 1, 11))
    horizon = HourlyHorizon(start, start.add_hours(2))
    for offset in (-1, 3):
        with pytest.raises(ValueError, match="boundaries"):
            horizon.date_at(offset)
        with pytest.raises(ValueError, match="boundaries"):
            horizon.offset_of(start.add_hours(offset))


@pytest.mark.parametrize(
    "values",
    [
        {"start": "1936.1.1", "deadline": "1936.1.2"},
        {"calendar": "gregorian", "start": "1936.1.1", "deadline": "1936.1.2"},
        {"calendar": "hoi4_no_leap", "start": "1936.1.1", "deadline": "1936.1.2", "hours": 24},
        None,
    ],
)
def test_horizon_serialization_never_infers_or_changes_calendar(values):
    with pytest.raises(ValueError):
        HourlyHorizon.from_dict(values)


@given(st.integers(min_value=0, max_value=10**12), st.integers(min_value=0, max_value=100_000))
def test_integer_hour_round_trip_and_split_horizons(index, duration):
    start = CampaignDate.from_hour_index(index)
    assert start.to_hour_index() == index
    middle = start.add_hours(duration // 2)
    deadline = start.add_hours(duration)
    complete = HourlyHorizon(start, deadline)
    before, after = HourlyHorizon(start, middle), HourlyHorizon(middle, deadline)
    assert before.hours + after.hours == complete.hours == duration
    assert before.date_at(before.hours) == after.start
    assert complete.date_at(duration) == deadline
