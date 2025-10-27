"""
Unit tests for Phase 2: Country and Idea functionality.

Tests the Country class, Idea model, and IdeaParser.
"""

import unittest
from games.hoi4.core.country import Country
from games.hoi4.models.idea import Idea, IdeaCategory, IdeaSlot
from games.hoi4.state import State, StateCategory


class TestIdea(unittest.TestCase):
    """Test cases for the Idea model."""
    
    def test_idea_creation(self):
        """Test creating an Idea."""
        idea = Idea(
            name="test_idea",
            category=IdeaCategory.COUNTRY,
            cost=100,
            modifier={"stability_factor": 0.05}
        )
        
        self.assertEqual(idea.name, "test_idea")
        self.assertEqual(idea.category, IdeaCategory.COUNTRY)
        self.assertEqual(idea.cost, 100)
        self.assertEqual(idea.get_modifier_value("stability_factor"), 0.05)
    
    def test_idea_is_law(self):
        """Test is_law() method."""
        economy_idea = Idea(name="test", category=IdeaCategory.ECONOMY)
        trade_idea = Idea(name="test", category=IdeaCategory.TRADE)
        manpower_idea = Idea(name="test", category=IdeaCategory.MANPOWER)
        spirit_idea = Idea(name="test", category=IdeaCategory.COUNTRY)
        
        self.assertTrue(economy_idea.is_law())
        self.assertTrue(trade_idea.is_law())
        self.assertTrue(manpower_idea.is_law())
        self.assertFalse(spirit_idea.is_law())
    
    def test_idea_is_advisor(self):
        """Test is_advisor() method."""
        advisor = Idea(name="test", category=IdeaCategory.POLITICAL_ADVISOR)
        chief = Idea(name="test", category=IdeaCategory.ARMY_CHIEF)
        spirit = Idea(name="test", category=IdeaCategory.COUNTRY)
        
        self.assertTrue(advisor.is_advisor())
        self.assertTrue(chief.is_advisor())
        self.assertFalse(spirit.is_advisor())


class TestIdeaSlot(unittest.TestCase):
    """Test cases for the IdeaSlot class."""
    
    def test_idea_slot_creation(self):
        """Test creating an IdeaSlot."""
        slot = IdeaSlot(category=IdeaCategory.ECONOMY)
        
        self.assertEqual(slot.category, IdeaCategory.ECONOMY)
        self.assertIsNone(slot.current_idea)
    
    def test_set_matching_idea(self):
        """Test setting an idea with matching category."""
        slot = IdeaSlot(category=IdeaCategory.ECONOMY)
        idea = Idea(name="test", category=IdeaCategory.ECONOMY)
        
        success = slot.set_idea(idea)
        
        self.assertTrue(success)
        self.assertEqual(slot.current_idea, idea)
    
    def test_set_mismatched_idea(self):
        """Test setting an idea with wrong category raises error."""
        slot = IdeaSlot(category=IdeaCategory.ECONOMY)
        idea = Idea(name="test", category=IdeaCategory.TRADE)
        
        with self.assertRaises(ValueError):
            slot.set_idea(idea)


class TestCountry(unittest.TestCase):
    """Test cases for the Country class."""
    
    def test_country_creation(self):
        """Test creating a Country."""
        country = Country(
            name="Test Nation",
            tag="TST",
            political_power=100.0,
            stability=0.6,
            war_support=0.5
        )
        
        self.assertEqual(country.name, "Test Nation")
        self.assertEqual(country.tag, "TST")
        self.assertEqual(country.political_power, 100.0)
        self.assertEqual(country.stability, 0.6)
        self.assertEqual(country.war_support, 0.5)
    
    def test_country_invalid_stability(self):
        """Test that invalid stability raises error."""
        with self.assertRaises(ValueError):
            Country(name="Test", stability=1.5)
        
        with self.assertRaises(ValueError):
            Country(name="Test", stability=-0.1)
    
    def test_country_invalid_war_support(self):
        """Test that invalid war support raises error."""
        with self.assertRaises(ValueError):
            Country(name="Test", war_support=1.5)
    
    def test_add_national_spirit(self):
        """Test adding a national spirit."""
        country = Country(name="Test")
        spirit = Idea(
            name="militarism",
            category=IdeaCategory.COUNTRY,
            modifier={"army_org_factor": 0.05}
        )
        
        country.add_national_spirit(spirit)
        
        self.assertEqual(len(country.national_spirits), 1)
        self.assertEqual(country.national_spirits[0].name, "militarism")
    
    def test_add_non_spirit_as_spirit(self):
        """Test that non-spirit ideas can't be added as spirits."""
        country = Country(name="Test")
        law = Idea(name="test", category=IdeaCategory.ECONOMY)
        
        with self.assertRaises(ValueError):
            country.add_national_spirit(law)
    
    def test_remove_national_spirit(self):
        """Test removing a national spirit."""
        country = Country(name="Test")
        spirit = Idea(name="test_spirit", category=IdeaCategory.COUNTRY)
        
        country.add_national_spirit(spirit)
        self.assertEqual(len(country.national_spirits), 1)
        
        removed = country.remove_national_spirit("test_spirit")
        
        self.assertTrue(removed)
        self.assertEqual(len(country.national_spirits), 0)
    
    def test_get_national_spirit(self):
        """Test getting a national spirit by name."""
        country = Country(name="Test")
        spirit = Idea(name="test_spirit", category=IdeaCategory.COUNTRY)
        
        country.add_national_spirit(spirit)
        found = country.get_national_spirit("test_spirit")
        
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "test_spirit")
    
    def test_set_law(self):
        """Test setting an economic law."""
        country = Country(name="Test", political_power=200.0)
        law = Idea(
            name="civilian_economy",
            category=IdeaCategory.ECONOMY,
            cost=150,
            modifier={"consumer_goods_factor": 0.30}
        )
        
        success = country.set_law(law)
        
        self.assertTrue(success)
        self.assertEqual(country.political_power, 50.0)
        self.assertEqual(country.get_current_law(IdeaCategory.ECONOMY), law)
    
    def test_set_law_insufficient_pp(self):
        """Test that law can't be set without enough PP."""
        country = Country(name="Test", political_power=50.0)
        law = Idea(name="test", category=IdeaCategory.ECONOMY, cost=150)
        
        success = country.set_law(law)
        
        self.assertFalse(success)
    
    def test_total_resources(self):
        """Test calculating total resources across states."""
        country = Country(name="Test")
        
        state1 = State(name="State1")
        state1.set_resource("oil", 10.0)
        state1.set_resource("steel", 20.0)
        
        state2 = State(name="State2")
        state2.set_resource("oil", 15.0)
        state2.set_resource("aluminum", 5.0)
        
        country.add_state(state1)
        country.add_state(state2)
        
        total = country.total_resources()
        
        self.assertEqual(total["oil"], 25.0)
        self.assertEqual(total["steel"], 20.0)
        self.assertEqual(total["aluminum"], 5.0)
    
    def test_get_resource(self):
        """Test getting a specific resource total."""
        country = Country(name="Test")
        
        state1 = State(name="State1")
        state1.set_resource("oil", 10.0)
        
        state2 = State(name="State2")
        state2.set_resource("oil", 15.0)
        
        country.add_state(state1)
        country.add_state(state2)
        
        self.assertEqual(country.get_resource("oil"), 25.0)
        self.assertEqual(country.get_resource("steel"), 0.0)
    
    def test_total_manpower(self):
        """Test calculating total manpower."""
        country = Country(name="Test")
        
        state1 = State(name="State1", manpower=1000000)
        state2 = State(name="State2", manpower=500000)
        
        country.add_state(state1)
        country.add_state(state2)
        
        self.assertEqual(country.total_manpower(), 1500000)
    
    def test_total_victory_points(self):
        """Test calculating total victory points."""
        country = Country(name="Test")
        
        state1 = State(name="State1", victory_points=20)
        state2 = State(name="State2", victory_points=10)
        
        country.add_state(state1)
        country.add_state(state2)
        
        self.assertEqual(country.total_victory_points(), 30)
    
    def test_country_inherits_faction_methods(self):
        """Test that Country inherits Faction methods."""
        country = Country(name="Test")
        
        state1 = State(name="State1", civilian_factories=5, military_factories=3)
        state2 = State(name="State2", civilian_factories=4, military_factories=2)
        
        country.add_state(state1)
        country.add_state(state2)
        
        self.assertEqual(country.total_civilian_factories(), 9)
        self.assertEqual(country.total_military_factories(), 5)
        self.assertEqual(country.total_factories(), 14)


if __name__ == '__main__':
    unittest.main()
