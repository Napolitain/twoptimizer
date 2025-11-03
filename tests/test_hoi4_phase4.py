"""
Tests for Phase 4 implementation: Time simulation, Equipment, Production, and Optimization.

This test suite covers:
- GameDate and GameClock (time simulation)
- Equipment models and database
- Production and ProductionLine models
- ProductionOptimizer with OR-Tools integration
"""

import unittest
from games.hoi4.models.game_date import GameDate, GameClock, HISTORICAL_DATES
from games.hoi4.models.equipment import (
    Equipment, EquipmentType, EquipmentCategory,
    create_infantry_equipment, create_artillery,
    get_equipment, get_equipment_by_type, EQUIPMENT_DATABASE
)
from games.hoi4.models.production import Production, ProductionLine
from games.hoi4.optimization import ProductionOptimizer
from games.hoi4.optimization.production_optimizer import ProductionGoal


class TestGameDate(unittest.TestCase):
    """Tests for GameDate class."""
    
    def test_game_date_creation(self):
        """Test creating a GameDate."""
        date = GameDate(1936, 1, 1)
        self.assertEqual(date.year, 1936)
        self.assertEqual(date.month, 1)
        self.assertEqual(date.day, 1)
        self.assertEqual(date.hour, 0)
    
    def test_game_date_validation(self):
        """Test GameDate validation."""
        with self.assertRaises(ValueError):
            GameDate(1935, 1, 1)  # Too early
        with self.assertRaises(ValueError):
            GameDate(1936, 13, 1)  # Invalid month
        with self.assertRaises(ValueError):
            GameDate(1936, 1, 32)  # Invalid day
    
    def test_add_days(self):
        """Test adding days to a date."""
        date = GameDate(1936, 1, 1)
        new_date = date.add_days(30)
        self.assertEqual(new_date.month, 1)
        self.assertEqual(new_date.day, 31)
    
    def test_days_until(self):
        """Test calculating days between dates."""
        date1 = GameDate(1936, 1, 1)
        date2 = GameDate(1936, 1, 31)
        days = date1.days_until(date2)
        self.assertEqual(days, 30)
    
    def test_date_comparison(self):
        """Test date comparison operators."""
        date1 = GameDate(1936, 1, 1)
        date2 = GameDate(1936, 12, 31)
        self.assertLess(date1, date2)
        self.assertGreater(date2, date1)
        self.assertLessEqual(date1, date2)
        self.assertEqual(date1, GameDate(1936, 1, 1))
    
    def test_historical_dates(self):
        """Test historical dates dictionary."""
        self.assertIn("game_start", HISTORICAL_DATES)
        self.assertIn("war_start", HISTORICAL_DATES)
        self.assertEqual(HISTORICAL_DATES["game_start"].year, 1936)
        self.assertEqual(HISTORICAL_DATES["war_start"].year, 1939)


class TestGameClock(unittest.TestCase):
    """Tests for GameClock class."""
    
    def test_clock_initialization(self):
        """Test creating a GameClock."""
        clock = GameClock()
        self.assertEqual(clock.current_date.year, 1936)
        self.assertEqual(clock.current_date.month, 1)
        self.assertEqual(clock.current_date.day, 1)
    
    def test_advance_days(self):
        """Test advancing the clock by days."""
        clock = GameClock()
        new_date = clock.advance_days(366)  # 1936 is a leap year
        self.assertEqual(new_date.year, 1937)
        self.assertEqual(clock.elapsed_days(), 366)
    
    def test_advance_to_date(self):
        """Test advancing to a specific date."""
        clock = GameClock()
        target = GameDate(1939, 9, 1)
        days = clock.advance_to_date(target)
        self.assertEqual(clock.current_date, target)
        self.assertGreater(days, 1000)
    
    def test_reset(self):
        """Test resetting the clock."""
        clock = GameClock()
        clock.advance_days(100)
        clock.reset()
        self.assertEqual(clock.elapsed_days(), 0)


class TestEquipment(unittest.TestCase):
    """Tests for Equipment class."""
    
    def test_equipment_creation(self):
        """Test creating equipment."""
        eq = create_infantry_equipment()
        self.assertEqual(eq.equipment_type, EquipmentType.INFANTRY_EQUIPMENT)
        self.assertEqual(eq.category, EquipmentCategory.INFANTRY)
        self.assertGreater(eq.production_cost, 0)
    
    def test_equipment_validation(self):
        """Test equipment validation."""
        with self.assertRaises(ValueError):
            Equipment(
                name="test",
                display_name="Test",
                equipment_type=EquipmentType.INFANTRY_EQUIPMENT,
                category=EquipmentCategory.INFANTRY,
                production_cost=-1.0  # Invalid
            )
    
    def test_daily_production_cost(self):
        """Test calculating daily production cost."""
        eq = create_infantry_equipment()
        daily = eq.get_daily_production_cost()
        self.assertGreater(daily, 0)
        self.assertEqual(daily, eq.production_cost / eq.production_time)
    
    def test_resource_requirements(self):
        """Test resource requirement methods."""
        eq = create_artillery()
        self.assertTrue(eq.has_resource_requirement("steel"))
        self.assertGreater(eq.get_resource_requirement("steel"), 0)
        self.assertGreater(eq.total_resource_cost(), 0)
    
    def test_equipment_database(self):
        """Test equipment database."""
        self.assertIn("infantry_equipment_1", EQUIPMENT_DATABASE)
        eq = get_equipment("infantry_equipment_1")
        self.assertIsNotNone(eq)
        self.assertEqual(eq.name, "infantry_equipment_1")
    
    def test_get_by_type(self):
        """Test getting equipment by type."""
        infantry = get_equipment_by_type(EquipmentType.INFANTRY_EQUIPMENT)
        self.assertGreater(len(infantry), 0)
        for eq in infantry:
            self.assertEqual(eq.equipment_type, EquipmentType.INFANTRY_EQUIPMENT)


class TestProductionLine(unittest.TestCase):
    """Tests for ProductionLine class."""
    
    def test_production_line_creation(self):
        """Test creating a production line."""
        eq = create_infantry_equipment()
        line = ProductionLine(equipment=eq, assigned_factories=10.0)
        self.assertEqual(line.assigned_factories, 10.0)
        self.assertEqual(line.efficiency, 0.1)  # Starts at 10%
    
    def test_efficiency_calculation(self):
        """Test efficiency growth over time."""
        eq = create_infantry_equipment()
        start = GameDate(1936, 1, 1)
        line = ProductionLine(equipment=eq, assigned_factories=5.0, start_date=start)
        
        # After 0 days
        eff0 = line.calculate_efficiency(start)
        self.assertEqual(eff0, 0.1)
        
        # After 90 days (should be 0.1 + 0.9 = 1.0)
        date90 = start.add_days(90)
        eff90 = line.calculate_efficiency(date90)
        self.assertEqual(eff90, 1.0)
        
        # After 200 days (capped at 1.0)
        date200 = start.add_days(200)
        eff200 = line.calculate_efficiency(date200)
        self.assertEqual(eff200, 1.0)
    
    def test_daily_output(self):
        """Test calculating daily output."""
        eq = create_infantry_equipment()
        line = ProductionLine(equipment=eq, assigned_factories=10.0, efficiency=1.0)
        
        output = line.get_daily_output()
        self.assertGreater(output, 0)
    
    def test_output_by_date(self):
        """Test calculating total output by date."""
        eq = create_infantry_equipment()
        start = GameDate(1936, 1, 1)
        target = GameDate(1937, 1, 1)
        
        line = ProductionLine(equipment=eq, assigned_factories=10.0, start_date=start)
        total = line.calculate_output_by_date(target)
        self.assertGreater(total, 0)
    
    def test_resource_consumption(self):
        """Test calculating resource consumption."""
        eq = create_artillery()
        line = ProductionLine(equipment=eq, assigned_factories=5.0, efficiency=1.0)
        
        consumption = line.get_daily_resource_consumption()
        self.assertIn("steel", consumption)
        self.assertGreater(consumption["steel"], 0)


class TestProduction(unittest.TestCase):
    """Tests for Production class."""
    
    def test_production_creation(self):
        """Test creating a Production instance."""
        prod = Production(
            civilian_factories=20,
            military_factories=15,
            naval_factories=5
        )
        self.assertEqual(prod.civilian_factories, 20)
        self.assertEqual(prod.military_factories, 15)
        self.assertEqual(prod.naval_factories, 5)
    
    def test_add_production_line(self):
        """Test adding a production line."""
        prod = Production(military_factories=20)
        eq = create_infantry_equipment()
        
        line = prod.add_production_line(eq, 5.0)
        self.assertEqual(len(prod.production_lines), 1)
        self.assertEqual(line.assigned_factories, 5.0)
    
    def test_available_factories(self):
        """Test calculating available factories."""
        prod = Production(military_factories=20)
        eq = create_infantry_equipment()
        
        # Initially all available
        self.assertEqual(prod.get_available_military_factories(), 20.0)
        
        # After assignment
        prod.add_production_line(eq, 10.0)
        self.assertEqual(prod.get_available_military_factories(), 10.0)
    
    def test_total_daily_output(self):
        """Test calculating total daily output."""
        prod = Production(military_factories=20)
        eq1 = create_infantry_equipment()
        eq2 = create_artillery()
        
        prod.add_production_line(eq1, 10.0)
        prod.add_production_line(eq2, 5.0)
        
        output = prod.calculate_total_daily_output()
        self.assertEqual(len(output), 2)
        self.assertIn(eq1.name, output)
        self.assertIn(eq2.name, output)
    
    def test_resource_consumption(self):
        """Test calculating total resource consumption."""
        prod = Production(military_factories=20)
        eq = create_artillery()
        
        prod.add_production_line(eq, 10.0, priority=5)
        
        consumption = prod.calculate_total_resource_consumption()
        self.assertIn("steel", consumption)
        self.assertGreater(consumption["steel"], 0)


class TestProductionOptimizer(unittest.TestCase):
    """Tests for ProductionOptimizer class."""
    
    def test_optimizer_creation(self):
        """Test creating an optimizer."""
        optimizer = ProductionOptimizer()
        self.assertIsNotNone(optimizer)
    
    def test_single_equipment_optimization(self):
        """Test optimizing single equipment production."""
        optimizer = ProductionOptimizer()
        eq = create_infantry_equipment()
        
        start = GameDate(1936, 1, 1)
        target = GameDate(1937, 1, 1)
        
        output = optimizer.optimize_single_equipment(
            equipment=eq,
            available_factories=10.0,
            target_date=target,
            start_date=start
        )
        
        self.assertGreater(output, 0)
    
    def test_multi_equipment_optimization(self):
        """Test optimizing multiple equipment types."""
        optimizer = ProductionOptimizer()
        
        eq1 = create_infantry_equipment()
        eq2 = create_artillery()
        
        start = GameDate(1936, 1, 1)
        target = GameDate(1937, 1, 1)
        
        goals = [
            ProductionGoal(equipment=eq1, target_amount=1000, target_date=target, weight=1.0),
            ProductionGoal(equipment=eq2, target_amount=500, target_date=target, weight=1.0),
        ]
        
        result = optimizer.optimize_production(
            available_military_factories=20.0,
            available_naval_factories=5.0,
            goals=goals,
            start_date=start
        )
        
        self.assertIn(result.status, ["OPTIMAL", "FEASIBLE"])
        self.assertGreater(len(result.factory_allocations), 0)
    
    def test_optimization_with_resources(self):
        """Test optimization with resource constraints."""
        optimizer = ProductionOptimizer()
        
        eq = create_artillery()
        start = GameDate(1936, 1, 1)
        target = GameDate(1937, 1, 1)
        
        goals = [
            ProductionGoal(equipment=eq, target_amount=500, target_date=target),
        ]
        
        # Limited steel
        result = optimizer.optimize_production(
            available_military_factories=20.0,
            available_naval_factories=0.0,
            goals=goals,
            start_date=start,
            available_resources={"steel": 100.0}
        )
        
        self.assertIn(result.status, ["OPTIMAL", "FEASIBLE", "INFEASIBLE"])
    
    def test_maximize_output_mode(self):
        """Test optimization in maximize output mode."""
        optimizer = ProductionOptimizer()
        
        eq = create_infantry_equipment()
        start = GameDate(1936, 1, 1)
        target = GameDate(1937, 1, 1)
        
        goals = [
            ProductionGoal(equipment=eq, target_amount=10000, target_date=target),
        ]
        
        result = optimizer.optimize_production(
            available_military_factories=10.0,
            available_naval_factories=0.0,
            goals=goals,
            start_date=start,
            maximize_total_output=True
        )
        
        self.assertIn(result.status, ["OPTIMAL", "FEASIBLE"])
        if result.is_optimal:
            # Should allocate all factories
            total_allocated = sum(result.factory_allocations.values())
            self.assertAlmostEqual(total_allocated, 10.0, places=1)


if __name__ == '__main__':
    unittest.main()
