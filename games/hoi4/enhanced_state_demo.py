"""
Demo script showcasing the enhanced State class features.

This demonstrates the new capabilities added to the State class including:
- State categories with building slots
- Resource management
- State modifiers
- Province tracking
- Building slot calculations
"""

import sys
from pathlib import Path

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent.parent))

from games.hoi4 import State, StateCategory, Faction


def main():
    print("=" * 80)
    print("Hearts of Iron IV - Enhanced State Class Demo")
    print("=" * 80)
    print()
    
    # Demo 1: State Categories and Building Slots
    print("Demo 1: State Categories and Building Slots")
    print("-" * 80)
    
    industrial_state = State(
        name="Industrial Heartland",
        state_category=StateCategory.METROPOLIS,
        infrastructure=8,
        civilian_factories=10,
        military_factories=8,
        air_bases=3
    )
    
    print(f"State: {industrial_state.name}")
    print(f"Category: {industrial_state.state_category.category_name.title()}")
    print(f"Base building slots: {industrial_state.state_category.building_slots}")
    print(f"Infrastructure level: {industrial_state.infrastructure}")
    print(f"Max building slots: {industrial_state.get_max_building_slots()}")
    print(f"  (Base {industrial_state.state_category.building_slots} + Infrastructure bonus {industrial_state.infrastructure * 0.5})")
    print(f"Used slots: {industrial_state.get_used_building_slots()}")
    print(f"  (Civ factories: {industrial_state.civilian_factories}, Mil factories: {industrial_state.military_factories}, Air bases: {industrial_state.air_bases})")
    print(f"Free slots: {industrial_state.get_free_building_slots()}")
    print(f"Can build 2 more factories? {industrial_state.can_build(2)}")
    print()
    
    # Demo 2: Resource Management
    print("Demo 2: Resource Management")
    print("-" * 80)
    
    resource_state = State(
        name="Resource-Rich Region",
        state_category=StateCategory.RURAL,
        infrastructure=4,
        civilian_factories=2
    )
    
    # Set initial resources
    resource_state.set_resource("oil", 50.0)
    resource_state.set_resource("steel", 30.0)
    resource_state.set_resource("aluminum", 15.0)
    resource_state.set_resource("rubber", 20.0)
    
    print(f"State: {resource_state.name}")
    print(f"Resources:")
    for resource in ["oil", "steel", "aluminum", "rubber"]:
        amount = resource_state.get_resource(resource)
        print(f"  {resource.capitalize()}: {amount}")
    
    # Simulate resource consumption
    print(f"\nConsuming 10 oil...")
    resource_state.add_resource("oil", -10.0)
    print(f"  Oil remaining: {resource_state.get_resource('oil')}")
    print()
    
    # Demo 3: State Modifiers
    print("Demo 3: State Modifiers")
    print("-" * 80)
    
    modified_state = State(
        name="Boosted Production State",
        state_category=StateCategory.LARGE_CITY,
        civilian_factories=8
    )
    
    # Apply production bonuses
    modified_state.set_modifier("production_speed_buildings_factor", 0.10)
    modified_state.set_modifier("local_building_slots", 2.0)
    modified_state.set_modifier("local_resources_factor", 0.15)
    
    # Stack additional bonuses
    modified_state.add_modifier("production_speed_buildings_factor", 0.05)
    
    print(f"State: {modified_state.name}")
    print(f"Active modifiers:")
    for modifier_name, value in modified_state.state_modifiers.items():
        print(f"  {modifier_name}: {value:+.2f}")
    print()
    
    # Demo 4: Comprehensive State Example
    print("Demo 4: Comprehensive State with All Features")
    print("-" * 80)
    
    capital_state = State(
        name="Capital District",
        state_category=StateCategory.MEGALOPOLIS,
        infrastructure=10,
        civilian_factories=15,
        military_factories=10,
        air_bases=5,
        bunkers=3,
        manpower=5000000,
        victory_points=50,
        provinces=[101, 102, 103, 104]
    )
    
    # Add resources
    capital_state.set_resource("steel", 25.0)
    capital_state.set_resource("aluminum", 10.0)
    
    # Add modifiers
    capital_state.set_modifier("production_speed_buildings_factor", 0.20)
    capital_state.set_modifier("political_power_factor", 0.15)
    
    print(f"State: {capital_state.name}")
    print(f"  Category: {capital_state.state_category.category_name.title()}")
    print(f"  Manpower: {capital_state.manpower:,}")
    print(f"  Victory Points: {capital_state.victory_points}")
    print(f"  Provinces: {len(capital_state.provinces)}")
    print(f"  Total Factories: {capital_state.total_factories()}")
    print(f"  Building Slots: {capital_state.get_used_building_slots()}/{capital_state.get_max_building_slots()}")
    print(f"  Resources:")
    for resource, amount in capital_state.resources.items():
        print(f"    {resource.capitalize()}: {amount}")
    print(f"  Modifiers:")
    for modifier, value in capital_state.state_modifiers.items():
        print(f"    {modifier}: {value:+.2%}")
    print()
    
    # Demo 5: Faction with Enhanced States
    print("Demo 5: Faction with Enhanced States")
    print("-" * 80)
    
    custom_nation = Faction(name="Custom Nation")
    
    # Add multiple enhanced states
    custom_nation.add_state(capital_state)
    custom_nation.add_state(industrial_state)
    custom_nation.add_state(resource_state)
    
    print(f"Faction: {custom_nation.name}")
    print(f"Total States: {len(custom_nation.states)}")
    print(f"Total Factories: {custom_nation.total_factories()}")
    print(f"  Civilian: {custom_nation.total_civilian_factories()}")
    print(f"  Military: {custom_nation.total_military_factories()}")
    print(f"Average Infrastructure: {custom_nation.average_infrastructure():.1f}")
    print()
    
    print("State Summary:")
    for state in custom_nation.states:
        print(f"  {state.name}:")
        print(f"    Factories: {state.total_factories()}")
        if state.state_category:
            print(f"    Category: {state.state_category.category_name.title()}")
        print(f"    Building Slots: {state.get_free_building_slots()} free / {state.get_max_building_slots()} max")
        if state.resources:
            resource_list = ", ".join([f"{k}: {v}" for k, v in list(state.resources.items())[:2]])
            print(f"    Resources: {resource_list}")
    print()
    
    print("=" * 80)
    print("Demo Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
