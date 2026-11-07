"""Boundary and property tests for construction and modifier arithmetic."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from games.hoi4.models.building import Building, BuildingCategory, BuildingType
from games.hoi4.models.modifier import Modifier, ModifierManager, ModifierScope


def factory_type():
    return BuildingType(
        "factory",
        "Factory",
        BuildingCategory.INDUSTRIAL,
        base_cost=100,
        construction_time=5,
        max_level=5,
        modifiers={"state": {"output": 0.1}, "unknown": {"output": 99}},
    )


def test_construction_limits_damage_and_modifiers():
    building = Building(factory_type(), level=2, damage=0.5)
    assert building.effective_level == 1
    assert (
        building.get_current_modifiers().calculate_total_effect("output", ModifierScope.STATE)
        == 0.1
    )
    assert building.start_construction(2)
    assert building.total_level_when_complete == 4
    assert not building.start_construction(2)
    assert building.get_construction_cost(1) == 500
    assert building.get_construction_time(2) == 10
    assert building.complete_construction() == 2
    assert building.level == 4 and building.under_construction == 0
    assert building.repair(1) == 0.5
    assert building.take_damage(2) == 1
    assert "Factory" in str(building)
    assert "level=4" in repr(building)


@pytest.mark.parametrize(
    "values",
    [
        {"level": -1},
        {"under_construction": -1},
        {"damage": -0.1},
        {"damage": 1.1},
        {"construction_progress": -0.1},
        {"construction_progress": 1.1},
    ],
)
def test_building_rejects_invalid_states(values):
    with pytest.raises(ValueError):
        Building(factory_type(), **values)


@given(st.integers(0, 5), st.integers(0, 5))
def test_completed_construction_never_exceeds_building_limit(level, requested):
    building = Building(factory_type(), level=level)
    started = building.start_construction(requested)
    assert started == (requested > 0 and level + requested <= 5)
    completed = building.complete_construction()
    assert completed == (requested if started else 0)
    assert building.level == level + completed <= 5


def test_modifier_scope_controller_filter_and_combination():
    first = Modifier("first", ModifierScope.STATE, {"output": 2}, ["GER"], duration=10)
    second = Modifier(
        "second", ModifierScope.STATE, {"output": 3, "growth": 1}, ["SOV"], duration=5
    )
    combined = first.combine_with(second)
    assert combined.duration == 5
    assert combined.effects == {"output": 5, "growth": 1}
    assert combined.enable_for_controllers is not None
    assert set(combined.enable_for_controllers) == {"GER", "SOV"}
    permanent = Modifier("permanent", ModifierScope.STATE, {})
    assert permanent.combine_with(permanent).duration is None
    assert permanent.combine_with(first).duration == 10
    assert first.get_effect("missing") == 0
    assert first.has_effect("output")
    copy = first.get_all_effects()
    copy["output"] = 99
    assert first.get_effect("output") == 2
    with pytest.raises(ValueError, match="different scopes"):
        first.combine_with(Modifier("country", ModifierScope.COUNTRY, {}))
    manager = ModifierManager()
    manager.add_modifier(first)
    manager.add_modifier(second)
    manager.add_modifier(permanent)
    assert manager.calculate_total_effect("output", ModifierScope.STATE, "GER") == 2
    assert manager.get_all_effects(ModifierScope.STATE, "SOV") == {"output": 3, "growth": 1}
    assert manager.get_all_effects(ModifierScope.COUNTRY) == {}
    assert len(list(manager)) == len(manager) == 3
    assert "first" in str(first) and "effects=" in repr(first)
    assert manager.remove_modifier("first")
    assert not manager.remove_modifier("missing")
    manager.clear()
    assert len(manager) == 0


def test_simple_modifier_sources_and_additive_values():
    manager = ModifierManager()
    manager.add_modifier("output", 0.1, "factory")
    manager.add_modifier("output", 0.2)
    assert manager.get_modifier("output") == pytest.approx(0.3)
    copy = manager.get_all_modifiers()
    copy["output"] = 99
    assert manager.get_modifier("output") == pytest.approx(0.3)
    assert manager.remove_modifier("output", "factory")
    assert manager.get_modifier("output") == 0
