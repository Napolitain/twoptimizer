"""
Unit tests for HoI4 game module.

Tests the Region, Faction, and example faction functionality.
"""

import unittest
from games.hoi4 import (
    Region,
    Faction,
    create_france_faction,
    create_germany_faction,
    create_soviet_union_faction,
)


class TestRegion(unittest.TestCase):
    """Test cases for the Region class."""
    
    def test_region_creation(self):
        """Test creating a basic region."""
        region = Region(
            name="Test Region",
            civilian_factories=5,
            military_factories=3,
            infrastructure=6,
            bunkers=2
        )
        
        self.assertEqual(region.name, "Test Region")
        self.assertEqual(region.civilian_factories, 5)
        self.assertEqual(region.military_factories, 3)
        self.assertEqual(region.infrastructure, 6)
        self.assertEqual(region.bunkers, 2)
    
    def test_region_with_defaults(self):
        """Test creating a region with default values."""
        region = Region(name="Default Region")
        
        self.assertEqual(region.name, "Default Region")
        self.assertEqual(region.civilian_factories, 0)
        self.assertEqual(region.military_factories, 0)
        self.assertEqual(region.infrastructure, 0)
        self.assertEqual(region.bunkers, 0)
        self.assertIsNone(region.naval_bases)
        self.assertIsNone(region.air_bases)
    
    def test_region_with_naval_and_air_bases(self):
        """Test creating a region with naval and air bases."""
        region = Region(
            name="Coastal Region",
            civilian_factories=4,
            military_factories=2,
            infrastructure=5,
            bunkers=1,
            naval_bases=3,
            air_bases=2
        )
        
        self.assertEqual(region.naval_bases, 3)
        self.assertEqual(region.air_bases, 2)
    
    def test_total_factories(self):
        """Test calculating total factories."""
        region = Region(
            name="Industrial Region",
            civilian_factories=10,
            military_factories=8,
            infrastructure=7,
            bunkers=0
        )
        
        self.assertEqual(region.total_factories(), 18)
    
    def test_negative_civilian_factories(self):
        """Test that negative civilian factories raise ValueError."""
        with self.assertRaises(ValueError) as context:
            Region(
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
            Region(
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
            Region(
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
            Region(
                name="Invalid Region",
                civilian_factories=5,
                military_factories=3,
                infrastructure=5,
                bunkers=-2
            )
        self.assertIn("Bunkers cannot be negative", str(context.exception))
    
    def test_region_repr(self):
        """Test the string representation of a region."""
        region = Region(
            name="Test Region",
            civilian_factories=5,
            military_factories=3,
            infrastructure=6,
            bunkers=2
        )
        
        repr_str = repr(region)
        self.assertIn("Test Region", repr_str)
        self.assertIn("civilian_factories=5", repr_str)
        self.assertIn("military_factories=3", repr_str)


class TestFaction(unittest.TestCase):
    """Test cases for the Faction class."""
    
    def test_faction_creation(self):
        """Test creating a basic faction."""
        faction = Faction(name="Test Faction")
        
        self.assertEqual(faction.name, "Test Faction")
        self.assertEqual(len(faction.regions), 0)
    
    def test_add_region(self):
        """Test adding regions to a faction."""
        faction = Faction(name="Test Faction")
        region1 = Region(name="Region 1", civilian_factories=5, military_factories=3)
        region2 = Region(name="Region 2", civilian_factories=4, military_factories=2)
        
        faction.add_region(region1)
        faction.add_region(region2)
        
        self.assertEqual(len(faction.regions), 2)
        self.assertEqual(faction.regions[0].name, "Region 1")
        self.assertEqual(faction.regions[1].name, "Region 2")
    
    def test_total_civilian_factories(self):
        """Test calculating total civilian factories."""
        faction = Faction(name="Test Faction")
        faction.add_region(Region(name="Region 1", civilian_factories=5, military_factories=3))
        faction.add_region(Region(name="Region 2", civilian_factories=4, military_factories=2))
        faction.add_region(Region(name="Region 3", civilian_factories=6, military_factories=4))
        
        self.assertEqual(faction.total_civilian_factories(), 15)
    
    def test_total_military_factories(self):
        """Test calculating total military factories."""
        faction = Faction(name="Test Faction")
        faction.add_region(Region(name="Region 1", civilian_factories=5, military_factories=3))
        faction.add_region(Region(name="Region 2", civilian_factories=4, military_factories=2))
        faction.add_region(Region(name="Region 3", civilian_factories=6, military_factories=4))
        
        self.assertEqual(faction.total_military_factories(), 9)
    
    def test_total_factories(self):
        """Test calculating total factories."""
        faction = Faction(name="Test Faction")
        faction.add_region(Region(name="Region 1", civilian_factories=5, military_factories=3))
        faction.add_region(Region(name="Region 2", civilian_factories=4, military_factories=2))
        
        self.assertEqual(faction.total_factories(), 14)
    
    def test_average_infrastructure(self):
        """Test calculating average infrastructure."""
        faction = Faction(name="Test Faction")
        faction.add_region(Region(name="Region 1", infrastructure=6))
        faction.add_region(Region(name="Region 2", infrastructure=8))
        faction.add_region(Region(name="Region 3", infrastructure=4))
        
        self.assertAlmostEqual(faction.average_infrastructure(), 6.0)
    
    def test_average_infrastructure_empty_faction(self):
        """Test average infrastructure for empty faction."""
        faction = Faction(name="Empty Faction")
        
        self.assertEqual(faction.average_infrastructure(), 0.0)
    
    def test_total_bunkers(self):
        """Test calculating total bunkers."""
        faction = Faction(name="Test Faction")
        faction.add_region(Region(name="Region 1", bunkers=2))
        faction.add_region(Region(name="Region 2", bunkers=3))
        faction.add_region(Region(name="Region 3", bunkers=1))
        
        self.assertEqual(faction.total_bunkers(), 6)
    
    def test_get_region(self):
        """Test getting a region by name."""
        faction = Faction(name="Test Faction")
        region1 = Region(name="Region 1", civilian_factories=5)
        region2 = Region(name="Region 2", civilian_factories=4)
        
        faction.add_region(region1)
        faction.add_region(region2)
        
        found_region = faction.get_region("Region 2")
        self.assertEqual(found_region.name, "Region 2")
        self.assertEqual(found_region.civilian_factories, 4)
    
    def test_get_region_not_found(self):
        """Test getting a non-existent region raises ValueError."""
        faction = Faction(name="Test Faction")
        faction.add_region(Region(name="Region 1"))
        
        with self.assertRaises(ValueError) as context:
            faction.get_region("Non-existent Region")
        self.assertIn("Region 'Non-existent Region' not found", str(context.exception))
    
    def test_faction_repr(self):
        """Test the string representation of a faction."""
        faction = Faction(name="Test Faction")
        faction.add_region(Region(name="Region 1", civilian_factories=5, military_factories=3))
        faction.add_region(Region(name="Region 2", civilian_factories=4, military_factories=2))
        
        repr_str = repr(faction)
        self.assertIn("Test Faction", repr_str)
        self.assertIn("regions=2", repr_str)
        self.assertIn("total_factories=14", repr_str)


class TestExampleFactions(unittest.TestCase):
    """Test cases for example faction creation."""
    
    def test_create_france_faction(self):
        """Test creating the France faction."""
        france = create_france_faction()
        
        self.assertEqual(france.name, "France")
        self.assertGreater(len(france.regions), 0)
        self.assertGreater(france.total_civilian_factories(), 0)
        self.assertGreater(france.total_military_factories(), 0)
        
        # Check that Paris exists
        paris = france.get_region("Paris")
        self.assertIsNotNone(paris)
        self.assertGreater(paris.civilian_factories, 0)
    
    def test_create_germany_faction(self):
        """Test creating the Germany faction."""
        germany = create_germany_faction()
        
        self.assertEqual(germany.name, "Germany")
        self.assertGreater(len(germany.regions), 0)
        self.assertGreater(germany.total_civilian_factories(), 0)
        self.assertGreater(germany.total_military_factories(), 0)
        
        # Check that Berlin exists
        berlin = germany.get_region("Berlin")
        self.assertIsNotNone(berlin)
        self.assertGreater(berlin.civilian_factories, 0)
    
    def test_create_soviet_union_faction(self):
        """Test creating the Soviet Union faction."""
        soviet_union = create_soviet_union_faction()
        
        self.assertEqual(soviet_union.name, "Soviet Union")
        self.assertGreater(len(soviet_union.regions), 0)
        self.assertGreater(soviet_union.total_civilian_factories(), 0)
        self.assertGreater(soviet_union.total_military_factories(), 0)
        
        # Check that Moscow exists
        moscow = soviet_union.get_region("Moscow")
        self.assertIsNotNone(moscow)
        self.assertGreater(moscow.civilian_factories, 0)
    
    def test_france_has_all_regions(self):
        """Test that France has all expected regions."""
        france = create_france_faction()
        
        expected_regions = ["Paris", "Normandy", "Lorraine", "Provence", "Brittany"]
        for region_name in expected_regions:
            region = france.get_region(region_name)
            self.assertIsNotNone(region)
    
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


if __name__ == '__main__':
    unittest.main()
