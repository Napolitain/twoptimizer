"""
Demonstration of HOI4 production optimization features.

This script demonstrates:
1. Setting up game time and dates
2. Creating equipment and production lines
3. Optimizing factory allocation to meet production goals
4. Analyzing results and resource consumption
"""

from games.hoi4 import (
    GameClock, HISTORICAL_DATES,
    Production,
    ProductionOptimizer
)
from games.hoi4.models.equipment import (
    create_infantry_equipment, create_artillery, 
    create_light_tank, create_fighter
)
from games.hoi4.optimization.production_optimizer import ProductionGoal


def demo_time_simulation():
    """Demonstrate time simulation capabilities."""
    print("=" * 70)
    print("TIME SIMULATION DEMO")
    print("=" * 70)
    
    # Create a game clock starting at game start
    clock = GameClock(start_date=HISTORICAL_DATES["game_start"])
    print(f"\nGame starts: {clock.current_date}")
    print(f"Historical war start: {HISTORICAL_DATES['war_start']}")
    
    # Advance to war start
    days = clock.advance_to_date(HISTORICAL_DATES["war_start"])
    print(f"\nAdvanced {days} days to: {clock.current_date}")
    print(f"Total elapsed: {clock.elapsed_days()} days")
    
    # Show some other historical dates
    print(f"\nOther key dates:")
    print(f"  Barbarossa: {HISTORICAL_DATES['barbarossa']}")
    print(f"  Pearl Harbor: {HISTORICAL_DATES['pearl_harbor']}")
    print(f"  D-Day: {HISTORICAL_DATES['d_day']}")
    print()


def demo_equipment_and_production():
    """Demonstrate equipment models and production lines."""
    print("=" * 70)
    print("EQUIPMENT & PRODUCTION DEMO")
    print("=" * 70)
    
    # Create some equipment
    infantry_eq = create_infantry_equipment()
    artillery_eq = create_artillery()
    tank_eq = create_light_tank()
    
    print(f"\nEquipment types:")
    print(f"  {infantry_eq.display_name}:")
    print(f"    Cost: {infantry_eq.production_cost} IC")
    print(f"    Time: {infantry_eq.production_time} days")
    print(f"    Resources: {infantry_eq.resource_cost}")
    
    print(f"\n  {artillery_eq.display_name}:")
    print(f"    Cost: {artillery_eq.production_cost} IC")
    print(f"    Time: {artillery_eq.production_time} days")
    print(f"    Resources: {artillery_eq.resource_cost}")
    
    print(f"\n  {tank_eq.display_name}:")
    print(f"    Cost: {tank_eq.production_cost} IC")
    print(f"    Time: {tank_eq.production_time} days")
    print(f"    Resources: {tank_eq.resource_cost}")
    
    # Create production system
    production = Production(
        civilian_factories=30,
        military_factories=20,
        naval_factories=5
    )
    
    # Set up production lines
    start_date = HISTORICAL_DATES["game_start"]
    
    production.add_production_line(infantry_eq, 10.0, start_date, priority=8)
    production.add_production_line(artillery_eq, 5.0, start_date, priority=5)
    production.add_production_line(tank_eq, 3.0, start_date, priority=6)
    
    print(f"\n\nProduction Setup:")
    print(f"  Total military factories: {production.military_factories}")
    print(f"  Available: {production.get_available_military_factories()}")
    print(f"\nProduction lines:")
    for i, line in enumerate(production.production_lines, 1):
        print(f"  {i}. {line}")
    
    # Calculate output at different dates
    print(f"\n\nProduction Analysis:")
    
    target_date = HISTORICAL_DATES["war_start"]
    print(f"\nBy {target_date} (war start):")
    
    for line in production.production_lines:
        output = line.calculate_output_by_date(target_date, start_date)
        print(f"  {line.equipment.display_name}: {output:.0f} units")
    
    # Resource consumption
    print(f"\nDaily resource consumption (at 100% efficiency):")
    consumption = production.calculate_total_resource_consumption(efficiency_modifiers=0.0)
    for resource, amount in consumption.items():
        print(f"  {resource}: {amount:.2f} per day")
    print()


def demo_production_optimization():
    """Demonstrate production optimization with OR-Tools."""
    print("=" * 70)
    print("PRODUCTION OPTIMIZATION DEMO")
    print("=" * 70)
    
    print("\nScenario: Germany preparing for war")
    print("Goal: Optimize factory allocation to meet equipment needs by Sept 1, 1939")
    
    # Setup
    start_date = HISTORICAL_DATES["game_start"]
    war_date = HISTORICAL_DATES["war_start"]
    
    available_military_factories = 25.0
    available_naval_factories = 5.0
    
    # Define production goals
    infantry_eq = create_infantry_equipment()
    artillery_eq = create_artillery()
    tank_eq = create_light_tank()
    fighter_eq = create_fighter()
    
    print(f"\nProduction goals by {war_date}:")
    print(f"  Infantry Equipment: 5,000 units (high priority)")
    print(f"  Artillery: 1,000 units (medium priority)")
    print(f"  Light Tanks: 500 units (medium priority)")
    print(f"  Fighters: 300 units (lower priority)")
    
    goals = [
        ProductionGoal(
            equipment=infantry_eq, 
            target_amount=5000, 
            target_date=war_date,
            weight=2.0  # Higher priority
        ),
        ProductionGoal(
            equipment=artillery_eq, 
            target_amount=1000, 
            target_date=war_date,
            weight=1.5
        ),
        ProductionGoal(
            equipment=tank_eq, 
            target_amount=500, 
            target_date=war_date,
            weight=1.5
        ),
        ProductionGoal(
            equipment=fighter_eq, 
            target_amount=300, 
            target_date=war_date,
            weight=1.0
        ),
    ]
    
    print(f"\nAvailable resources:")
    print(f"  Military factories: {available_military_factories}")
    print(f"  Naval factories: {available_naval_factories}")
    
    # Run optimization
    print(f"\nRunning optimization...")
    optimizer = ProductionOptimizer()
    
    result = optimizer.optimize_production(
        available_military_factories=available_military_factories,
        available_naval_factories=available_naval_factories,
        goals=goals,
        start_date=start_date,
        efficiency_modifiers=0.0,  # No bonuses
        maximize_total_output=False  # Minimize deviation from goals
    )
    
    print(f"\n{'-' * 70}")
    print(f"OPTIMIZATION RESULTS")
    print(f"{'-' * 70}")
    print(f"Status: {result.status}")
    print(f"Optimal: {result.is_optimal}")
    print(f"Execution time: {result.execution_time:.3f} seconds")
    
    print(f"\nOptimal factory allocations:")
    total_allocated = 0
    for eq_name, factories in result.factory_allocations.items():
        print(f"  {eq_name}: {factories:.2f} factories")
        total_allocated += factories
    print(f"  Total allocated: {total_allocated:.2f} / {available_military_factories}")
    
    print(f"\nExpected production by war start:")
    for eq_name, output in result.expected_output.items():
        # Find matching goal
        goal = next((g for g in goals if g.equipment.name == eq_name), None)
        if goal:
            target = goal.target_amount
            achievement = (output / target * 100) if target > 0 else 0
            print(f"  {eq_name}:")
            print(f"    Produced: {output:.0f} units")
            print(f"    Target: {target:.0f} units")
            print(f"    Achievement: {achievement:.1f}%")
    
    print(f"\nResource requirements:")
    for resource, amount in result.resource_usage.items():
        print(f"  {resource}: {amount:.2f} total")
    print()
    
    # Compare with maximize output mode
    print(f"\n{'-' * 70}")
    print("COMPARISON: Maximize Total Output Mode")
    print(f"{'-' * 70}")
    
    result_max = optimizer.optimize_production(
        available_military_factories=available_military_factories,
        available_naval_factories=available_naval_factories,
        goals=goals,
        start_date=start_date,
        efficiency_modifiers=0.0,
        maximize_total_output=True  # Different objective
    )
    
    print(f"\nFactory allocations (maximize mode):")
    for eq_name, factories in result_max.factory_allocations.items():
        print(f"  {eq_name}: {factories:.2f} factories")
    
    print(f"\nExpected output:")
    for eq_name, output in result_max.expected_output.items():
        print(f"  {eq_name}: {output:.0f} units")
    print()


def demo_resource_constrained_optimization():
    """Demonstrate optimization with resource constraints."""
    print("=" * 70)
    print("RESOURCE-CONSTRAINED OPTIMIZATION DEMO")
    print("=" * 70)
    
    print("\nScenario: Limited steel availability")
    
    start_date = HISTORICAL_DATES["game_start"]
    target_date = start_date.add_days(365)
    
    # Equipment that needs steel
    infantry_eq = create_infantry_equipment()
    artillery_eq = create_artillery()
    tank_eq = create_light_tank()
    
    goals = [
        ProductionGoal(equipment=infantry_eq, target_amount=3000, target_date=target_date),
        ProductionGoal(equipment=artillery_eq, target_amount=500, target_date=target_date),
        ProductionGoal(equipment=tank_eq, target_amount=200, target_date=target_date),
    ]
    
    # Limited resources
    available_resources = {
        "steel": 5000.0,  # Limited steel
        "tungsten": 1000.0,
        "chromium": 500.0,
    }
    
    print(f"\nAvailable resources:")
    for resource, amount in available_resources.items():
        print(f"  {resource}: {amount}")
    
    optimizer = ProductionOptimizer()
    
    result = optimizer.optimize_production(
        available_military_factories=20.0,
        available_naval_factories=0.0,
        goals=goals,
        start_date=start_date,
        available_resources=available_resources
    )
    
    print(f"\nOptimization result: {result.status}")
    
    if result.status in ["OPTIMAL", "FEASIBLE"]:
        print(f"\nOptimal allocations:")
        for eq_name, factories in result.factory_allocations.items():
            print(f"  {eq_name}: {factories:.2f} factories")
        
        print(f"\nResource usage:")
        for resource, used in result.resource_usage.items():
            available = available_resources.get(resource, float('inf'))
            utilization = (used / available * 100) if available > 0 else 0
            print(f"  {resource}: {used:.2f} / {available} ({utilization:.1f}%)")
    else:
        print(f"  Optimization was {result.status}")
        print(f"  This may indicate insufficient resources for goals")
    print()


def main():
    """Run all demonstrations."""
    print("\n")
    print("*" * 70)
    print("*" + " " * 68 + "*")
    print("*" + " " * 10 + "HOI4 PRODUCTION OPTIMIZATION DEMONSTRATION" + " " * 16 + "*")
    print("*" + " " * 68 + "*")
    print("*" * 70)
    print("\n")
    
    demo_time_simulation()
    print("\n")
    
    demo_equipment_and_production()
    print("\n")
    
    demo_production_optimization()
    print("\n")
    
    demo_resource_constrained_optimization()
    
    print("*" * 70)
    print("*" + " " * 68 + "*")
    print("*" + " " * 25 + "END OF DEMONSTRATION" + " " * 23 + "*")
    print("*" + " " * 68 + "*")
    print("*" * 70)
    print("\n")


if __name__ == "__main__":
    main()
