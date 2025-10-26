"""
Test for Smite 1 God Builder functionality.
"""

import unittest
from games.smite.smite1.data.gods.gods_loader import _ALL_GODS
from games.smite.smite1.data.items.items_loader import ALL_ITEMS
from games.smite.smite1.god_builder import GodBuilder
from games.smite.smite1.enums import PowerType


class TestGodBuilder(unittest.TestCase):
    """Test cases for GodBuilder optimization."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.gods = _ALL_GODS
        self.items = ALL_ITEMS
    
    def test_god_builder_physical_god(self):
        """Test optimization for a physical god."""
        god = self.gods['ah_muzen_cab']
        
        # Filter items for physical god
        relevant_items = [
            item for item in self.items 
            if item.stats and (
                item.stats.power_physical > 0 or 
                (item.stats.basic_attack_speed > 0 and item.stats.power_magical == 0)
            )
        ]
        
        # Ensure we have enough items
        self.assertGreaterEqual(len(relevant_items), 6)
        
        # Create builder and optimize
        builder = GodBuilder(god, relevant_items)
        result = builder.optimize_build()
        
        # Check result
        self.assertIsNotNone(result)
        build, dps = result
        
        # Check DPS is positive
        self.assertGreater(dps, 0)
        
        # Check that build has 6 items
        items_count = sum(
            1 for item in [build.item1, build.item2, build.item3, 
                          build.item4, build.item5, build.item6]
            if item is not None
        )
        self.assertEqual(items_count, 6)
        
        # Check DPS is better than base
        base_dps = god.get_dps_basic_attack()
        self.assertGreater(dps, base_dps)
    
    def test_god_builder_magical_god(self):
        """Test optimization for a magical god."""
        god = self.gods['agni']
        
        # Filter items for magical god
        relevant_items = [
            item for item in self.items 
            if item.stats and (
                item.stats.power_magical > 0 or 
                (item.stats.basic_attack_speed > 0 and item.stats.power_physical == 0)
            )
        ]
        
        # Ensure we have enough items
        self.assertGreaterEqual(len(relevant_items), 6)
        
        # Create builder and optimize
        builder = GodBuilder(god, relevant_items)
        result = builder.optimize_build()
        
        # Check result
        self.assertIsNotNone(result)
        build, dps = result
        
        # Check DPS is positive
        self.assertGreater(dps, 0)
        
        # Check that build has 6 items
        items_count = sum(
            1 for item in [build.item1, build.item2, build.item3, 
                          build.item4, build.item5, build.item6]
            if item is not None
        )
        self.assertEqual(items_count, 6)
    
    def test_dps_calculation_consistency(self):
        """Test that DPS calculations are consistent across methods."""
        god = self.gods['achilles']
        
        # Filter items
        relevant_items = [
            item for item in self.items 
            if item.stats and (
                item.stats.power_physical > 0 or 
                (item.stats.basic_attack_speed > 0 and item.stats.power_magical == 0)
            )
        ]
        
        # Optimize build
        builder = GodBuilder(god, relevant_items)
        result = builder.optimize_build()
        
        self.assertIsNotNone(result)
        build, builder_dps = result
        
        # Assign build to god
        god.build = build
        
        # Calculate DPS using god method
        god_dps = god.get_dps_basic_attack()
        
        # Calculate DPS using builder method
        items_list = [build.item1, build.item2, build.item3, 
                     build.item4, build.item5, build.item6]
        calculated_dps = builder.calculate_dps(items_list)
        
        # All should match within rounding error
        self.assertAlmostEqual(builder_dps, god_dps, places=1)
        self.assertAlmostEqual(builder_dps, calculated_dps, places=1)


if __name__ == '__main__':
    unittest.main()
