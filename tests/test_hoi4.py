"""
Unit tests for HoI4 game module.

Tests the Region, Faction, and example faction functionality.
"""

import unittest
from games.hoi4 import (
    State,
    Faction,
    create_france_faction,
    create_germany_faction,
    create_soviet_union_faction,
)


class TestState(unittest.TestCase):
    """Test cases for the Region class."""
    
    def test_region_creation(self):
        """Test creating a basic state."""
        state = State(
            name="Test Region",
            civilian_factories=5,
            military_factories=3,
            infrastructure=6,
            bunkers=2
        )
        
        self.assertEqual(state.name, "Test Region")
        self.assertEqual(state.civilian_factories, 5)
        self.assertEqual(state.military_factories, 3)
        self.assertEqual(state.infrastructure, 6)
        self.assertEqual(state.bunkers, 2)
    
    def test_region_with_defaults(self):
        """Test creating a region with default values."""
        state = State(name="Default Region")
        
        self.assertEqual(state.name, "Default Region")
        self.assertEqual(state.civilian_factories, 0)
        self.assertEqual(state.military_factories, 0)
        self.assertEqual(state.infrastructure, 0)
        self.assertEqual(state.bunkers, 0)
        self.assertIsNone(state.naval_bases)
        self.assertIsNone(state.air_bases)
    
    def test_region_with_naval_and_air_bases(self):
        """Test creating a region with naval and air bases."""
        state = State(
            name="Coastal Region",
            civilian_factories=4,
            military_factories=2,
            infrastructure=5,
            bunkers=1,
            naval_bases=3,
            air_bases=2
        )
        
        self.assertEqual(state.naval_bases, 3)
        self.assertEqual(state.air_bases, 2)
    
    def test_total_factories(self):
        """Test calculating total factories."""
        state = State(
            name="Industrial Region",
            civilian_factories=10,
            military_factories=8,
            infrastructure=7,
            bunkers=0
        )
        
        self.assertEqual(state.total_factories(), 18)
    
    def test_negative_civilian_factories(self):
        """Test that negative civilian factories raise ValueError."""
        with self.assertRaises(ValueError) as context:
            State(
                name="Invalid Region",
                civilian_factories=-5,
                military_factories=3,
                infrastructure=5,
                bunkers=0
            )
        self.assertIn("Civilian factories cannot be negative", str(context.exception))
    
    def test_negative_military_factories(self):
        """Test that negative military factories raise ValueError."""
        with self.assertRaises(ValueError) as context:
            State(
                name="Invalid Region",
                civilian_factories=5,
                military_factories=-3,
                infrastructure=5,
                bunkers=0
            )
        self.assertIn("Military factories cannot be negative", str(context.exception))
    
    def test_negative_infrastructure(self):
        """Test that negative infrastructure raises ValueError."""
        with self.assertRaises(ValueError) as context:
            State(
                name="Invalid Region",
                civilian_factories=5,
                military_factories=3,
                infrastructure=-5,
                bunkers=0
            )
        self.assertIn("Infrastructure cannot be negative", str(context.exception))
    
    def test_negative_bunkers(self):
        """Test that negative bunkers raise ValueError."""
        with self.assertRaises(ValueError) as context:
            State(
                name="Invalid Region",
                civilian_factories=5,
                military_factories=3,
                infrastructure=5,
                bunkers=-2
            )
        self.assertIn("Bunkers cannot be negative", str(context.exception))
    
    def test_region_repr(self):
        """Test the string representation of a state."""
        state = State(
            name="Test Region",
            civilian_factories=5,
            military_factories=3,
            infrastructure=6,
            bunkers=2
        )
        
        repr_str = repr(state)
        self.assertIn("Test Region", repr_str)
        self.assertIn("civilian_factories=5", repr_str)
        self.assertIn("military_factories=3", repr_str)


class TestFaction(unittest.TestCase):
    """Test cases for the Faction class."""
    
    def test_faction_creation(self):
        """Test creating a basic faction."""
        faction = Faction(name="Test Faction")
        
        self.assertEqual(faction.name, "Test Faction")
        self.assertEqual(len(faction.states), 0)
    
    def test_add_state(self):
        """Test adding regions to a faction."""
        faction = Faction(name="Test Faction")
        state1 = State(name="State 1", civilian_factories=5, military_factories=3)
        state2 = State(name="State 2", civilian_factories=4, military_factories=2)
        
        faction.add_state(state1)
        faction.add_state(state2)
        
        self.assertEqual(len(faction.states), 2)
        self.assertEqual(faction.states[0].name, "State 1")
        self.assertEqual(faction.states[1].name, "State 2")
    
    def test_total_civilian_factories(self):
        """Test calculating total civilian factories."""
        faction = Faction(name="Test Faction")
        faction.add_state(State(name="State 1", civilian_factories=5, military_factories=3))
        faction.add_state(State(name="State 2", civilian_factories=4, military_factories=2))
        faction.add_state(State(name="State 3", civilian_factories=6, military_factories=4))
        
        self.assertEqual(faction.total_civilian_factories(), 15)
    
    def test_total_military_factories(self):
        """Test calculating total military factories."""
        faction = Faction(name="Test Faction")
        faction.add_state(State(name="State 1", civilian_factories=5, military_factories=3))
        faction.add_state(State(name="State 2", civilian_factories=4, military_factories=2))
        faction.add_state(State(name="State 3", civilian_factories=6, military_factories=4))
        
        self.assertEqual(faction.total_military_factories(), 9)
    
    def test_total_factories(self):
        """Test calculating total factories."""
        faction = Faction(name="Test Faction")
        faction.add_state(State(name="State 1", civilian_factories=5, military_factories=3))
        faction.add_state(State(name="State 2", civilian_factories=4, military_factories=2))
        
        self.assertEqual(faction.total_factories(), 14)
    
    def test_average_infrastructure(self):
        """Test calculating average infrastructure."""
        faction = Faction(name="Test Faction")
        faction.add_state(State(name="State 1", infrastructure=6))
        faction.add_state(State(name="State 2", infrastructure=8))
        faction.add_state(State(name="State 3", infrastructure=4))
        
        self.assertAlmostEqual(faction.average_infrastructure(), 6.0)
    
    def test_average_infrastructure_empty_faction(self):
        """Test average infrastructure for empty faction."""
        faction = Faction(name="Empty Faction")
        
        self.assertEqual(faction.average_infrastructure(), 0.0)
    
    def test_total_bunkers(self):
        """Test calculating total bunkers."""
        faction = Faction(name="Test Faction")
        faction.add_state(State(name="State 1", bunkers=2))
        faction.add_state(State(name="State 2", bunkers=3))
        faction.add_state(State(name="State 3", bunkers=1))
        
        self.assertEqual(faction.total_bunkers(), 6)
    
    def test_get_state(self):
        """Test getting a region by name."""
        faction = Faction(name="Test Faction")
        state1 = State(name="State 1", civilian_factories=5)
        state2 = State(name="State 2", civilian_factories=4)
        
        faction.add_state(state1)
        faction.add_state(state2)
        
        found_state = faction.get_state("State 2")
        self.assertEqual(found_state.name, "State 2")
        self.assertEqual(found_state.civilian_factories, 4)
    
    def test_get_region_not_found(self):
        """Test getting a non-existent region raises ValueError."""
        faction = Faction(name="Test Faction")
        faction.add_state(State(name="State 1"))
        
        with self.assertRaises(ValueError) as context:
            faction.get_state("Non-existent Region")
        self.assertIn("State 'Non-existent Region' not found", str(context.exception))
    
    def test_faction_repr(self):
        """Test the string representation of a faction."""
        faction = Faction(name="Test Faction")
        faction.add_state(State(name="State 1", civilian_factories=5, military_factories=3))
        faction.add_state(State(name="State 2", civilian_factories=4, military_factories=2))
        
        repr_str = repr(faction)
        self.assertIn("Test Faction", repr_str)
        self.assertIn("states=2", repr_str)
        self.assertIn("total_factories=14", repr_str)


class TestExampleFactions(unittest.TestCase):
    """Test cases for example faction creation."""
    
    def test_create_france_faction(self):
        """Test creating the France faction."""
        france = create_france_faction()
        
        self.assertEqual(france.name, "France")
        self.assertGreater(len(france.states), 0)
        self.assertGreater(france.total_civilian_factories(), 0)
        self.assertGreater(france.total_military_factories(), 0)
        
        # Check that Paris exists
        paris = france.get_state("Paris")
        self.assertIsNotNone(paris)
        self.assertGreater(paris.civilian_factories, 0)
    
    def test_create_germany_faction(self):
        """Test creating the Germany faction."""
        germany = create_germany_faction()
        
        self.assertEqual(germany.name, "Germany")
        self.assertGreater(len(germany.states), 0)
        self.assertGreater(germany.total_civilian_factories(), 0)
        self.assertGreater(germany.total_military_factories(), 0)
        
        # Check that Berlin exists
        berlin = germany.get_state("Berlin")
        self.assertIsNotNone(berlin)
        self.assertGreater(berlin.civilian_factories, 0)
    
    def test_create_soviet_union_faction(self):
        """Test creating the Soviet Union faction."""
        soviet_union = create_soviet_union_faction()
        
        self.assertEqual(soviet_union.name, "Soviet Union")
        self.assertGreater(len(soviet_union.states), 0)
        self.assertGreater(soviet_union.total_civilian_factories(), 0)
        self.assertGreater(soviet_union.total_military_factories(), 0)
        
        # Check that Moscow exists
        moscow = soviet_union.get_state("Moscow")
        self.assertIsNotNone(moscow)
        self.assertGreater(moscow.civilian_factories, 0)
    
    def test_france_has_all_regions(self):
        """Test that France has all expected regions."""
        france = create_france_faction()
        
        expected_regions = ["Paris", "Normandy", "Lorraine", "Provence", "Brittany"]
        for region_name in expected_regions:
            state = france.get_state(region_name)
            self.assertIsNotNone(state)
    
    def test_france_total_factories(self):
        """Test France's total factory count."""
        france = create_france_faction()
        
        # Verify total factories match expected values
        # Paris: 8 + 4 = 12
        # Normandy: 3 + 2 = 5
        # Lorraine: 4 + 2 = 6
        # Provence: 3 + 1 = 4
        # Brittany: 2 + 1 = 3
        # Total: 30
        self.assertEqual(france.total_factories(), 30)
        self.assertEqual(france.total_civilian_factories(), 20)
        self.assertEqual(france.total_military_factories(), 10)


class TestEnhancedState(unittest.TestCase):
    """Test cases for enhanced State class features."""
    
    def test_state_category(self):
        """Test creating a state with a category."""
        from games.hoi4.state import StateCategory
        
        state = State(
            name="Test City",
            state_category=StateCategory.CITY
        )
        
        self.assertEqual(state.state_category, StateCategory.CITY)
        self.assertEqual(state.building_slots, 8)
    
    def test_manpower(self):
        """Test manpower attribute."""
        state = State(
            name="Test State",
            manpower=100000
        )
        
        self.assertEqual(state.manpower, 100000)
    
    def test_victory_points(self):
        """Test victory points attribute."""
        state = State(
            name="Capital",
            victory_points=50
        )
        
        self.assertEqual(state.victory_points, 50)
    
    def test_negative_manpower(self):
        """Test that negative manpower raises ValueError."""
        with self.assertRaises(ValueError):
            State(name="Invalid", manpower=-1000)
    
    def test_negative_victory_points(self):
        """Test that negative victory points raises ValueError."""
        with self.assertRaises(ValueError):
            State(name="Invalid", victory_points=-10)
    
    def test_resources(self):
        """Test resource management."""
        state = State(name="Resource State")
        
        # Initially no resources
        self.assertEqual(state.get_resource("oil"), 0.0)
        
        # Set resources
        state.set_resource("oil", 15.0)
        state.set_resource("steel", 25.0)
        
        self.assertEqual(state.get_resource("oil"), 15.0)
        self.assertEqual(state.get_resource("steel"), 25.0)
    
    def test_add_resource(self):
        """Test adding to resources."""
        state = State(name="Resource State")
        
        state.set_resource("oil", 10.0)
        state.add_resource("oil", 5.0)
        
        self.assertEqual(state.get_resource("oil"), 15.0)
    
    def test_negative_resource(self):
        """Test that negative resources raise ValueError."""
        state = State(name="Resource State")
        
        with self.assertRaises(ValueError):
            state.set_resource("oil", -10.0)
    
    def test_subtract_resource_below_zero(self):
        """Test that subtracting below zero raises ValueError."""
        state = State(name="Resource State")
        state.set_resource("oil", 5.0)
        
        with self.assertRaises(ValueError):
            state.add_resource("oil", -10.0)
    
    def test_building_slots(self):
        """Test building slot calculations."""
        from games.hoi4.state import StateCategory
        
        state = State(
            name="Test State",
            state_category=StateCategory.CITY,
            infrastructure=10,
            civilian_factories=3,
            military_factories=2
        )
        
        # City has 8 base slots, infrastructure 10 adds 5 more slots
        self.assertEqual(state.get_max_building_slots(), 13)
        
        # 5 factories are using slots
        self.assertEqual(state.get_used_building_slots(), 5)
        
        # 8 free slots remain
        self.assertEqual(state.get_free_building_slots(), 8)
    
    def test_can_build(self):
        """Test checking if building is possible."""
        from games.hoi4.state import StateCategory
        
        state = State(
            name="Test State",
            state_category=StateCategory.RURAL,
            civilian_factories=2,
            military_factories=1
        )
        
        # Rural has 4 slots, infrastructure 0 adds 0
        # Used: 3, Free: 1
        self.assertTrue(state.can_build(1))
        self.assertFalse(state.can_build(2))
    
    def test_state_modifiers(self):
        """Test state modifier management."""
        state = State(name="Test State")
        
        # Initially no modifiers
        self.assertEqual(state.get_modifier("production_speed_buildings_factor"), 0.0)
        
        # Set modifiers
        state.set_modifier("production_speed_buildings_factor", 0.1)
        state.set_modifier("local_building_slots", 2.0)
        
        self.assertEqual(state.get_modifier("production_speed_buildings_factor"), 0.1)
        self.assertEqual(state.get_modifier("local_building_slots"), 2.0)
    
    def test_add_modifier(self):
        """Test adding to modifiers."""
        state = State(name="Test State")
        
        state.set_modifier("production_speed_buildings_factor", 0.1)
        state.add_modifier("production_speed_buildings_factor", 0.05)
        
        self.assertAlmostEqual(state.get_modifier("production_speed_buildings_factor"), 0.15)
    
    def test_provinces(self):
        """Test province list attribute."""
        state = State(
            name="Test State",
            provinces=[123, 456, 789]
        )
        
        self.assertEqual(len(state.provinces), 3)
        self.assertIn(123, state.provinces)
        self.assertIn(456, state.provinces)
        self.assertIn(789, state.provinces)
    
    def test_max_building_slots_with_no_category(self):
        """Test building slots with no category set."""
        state = State(
            name="Test State",
            infrastructure=4
        )
        
        # No category, so base slots is 0, infrastructure adds 2
        self.assertEqual(state.get_max_building_slots(), 2)


if __name__ == '__main__':
    unittest.main()
