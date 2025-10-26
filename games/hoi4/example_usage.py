"""
Example usage of the HoI4 module.

This script demonstrates how to create and use factions and regions
in the Hearts of Iron IV optimization framework.
"""

from games.hoi4 import (
    Region,
    Faction,
    create_france_faction,
    create_germany_faction,
    create_soviet_union_faction,
)


def main():
    """Main function demonstrating HoI4 module usage."""
    print("=" * 60)
    print("Hearts of Iron IV - Faction and Region Example")
    print("=" * 60)
    print()
    
    # Example 1: Creating a custom faction with regions
    print("Example 1: Creating a custom faction")
    print("-" * 60)
    
    custom_faction = Faction(name="Custom Nation")
    
    # Add some regions
    capital = Region(
        name="Capital",
        civilian_factories=10,
        military_factories=5,
        infrastructure=8,
        bunkers=0,
        air_bases=5
    )
    
    industrial_region = Region(
        name="Industrial Hub",
        civilian_factories=15,
        military_factories=8,
        infrastructure=7,
        bunkers=2,
        air_bases=3
    )
    
    coastal_region = Region(
        name="Port City",
        civilian_factories=5,
        military_factories=3,
        infrastructure=6,
        bunkers=1,
        naval_bases=4,
        air_bases=2
    )
    
    custom_faction.add_region(capital)
    custom_faction.add_region(industrial_region)
    custom_faction.add_region(coastal_region)
    
    print(f"Faction: {custom_faction.name}")
    print(f"Number of regions: {len(custom_faction.regions)}")
    print(f"Total civilian factories: {custom_faction.total_civilian_factories()}")
    print(f"Total military factories: {custom_faction.total_military_factories()}")
    print(f"Total factories: {custom_faction.total_factories()}")
    print(f"Average infrastructure: {custom_faction.average_infrastructure():.2f}")
    print(f"Total bunkers: {custom_faction.total_bunkers()}")
    print()
    
    # Example 2: Using pre-built factions
    print("Example 2: Pre-built historical factions")
    print("-" * 60)
    
    france = create_france_faction()
    germany = create_germany_faction()
    soviet_union = create_soviet_union_faction()
    
    factions = [france, germany, soviet_union]
    
    for faction in factions:
        print(f"\n{faction.name}:")
        print(f"  Regions: {len(faction.regions)}")
        print(f"  Civilian factories: {faction.total_civilian_factories()}")
        print(f"  Military factories: {faction.total_military_factories()}")
        print(f"  Total factories: {faction.total_factories()}")
        print(f"  Average infrastructure: {faction.average_infrastructure():.2f}")
        print(f"  Total bunkers: {faction.total_bunkers()}")
    
    print()
    
    # Example 3: Detailed region information
    print("Example 3: Detailed region information for France")
    print("-" * 60)
    
    for region in france.regions:
        print(f"\n{region.name}:")
        print(f"  Civilian factories: {region.civilian_factories}")
        print(f"  Military factories: {region.military_factories}")
        print(f"  Total factories: {region.total_factories()}")
        print(f"  Infrastructure: {region.infrastructure}")
        print(f"  Bunkers: {region.bunkers}")
        if region.naval_bases is not None:
            print(f"  Naval bases: {region.naval_bases}")
        if region.air_bases is not None:
            print(f"  Air bases: {region.air_bases}")
    
    print()
    
    # Example 4: Accessing specific regions
    print("Example 4: Accessing specific regions")
    print("-" * 60)
    
    try:
        paris = france.get_region("Paris")
        print(f"Found region: {paris.name}")
        print(f"  {paris}")
        print()
        
        berlin = germany.get_region("Berlin")
        print(f"Found region: {berlin.name}")
        print(f"  {berlin}")
        print()
        
        moscow = soviet_union.get_region("Moscow")
        print(f"Found region: {moscow.name}")
        print(f"  {moscow}")
        print()
    except ValueError as e:
        print(f"Error: {e}")
    
    # Example 5: Comparison between factions
    print("Example 5: Faction comparison")
    print("-" * 60)
    
    print("\nFactory Production Comparison:")
    print(f"{'Faction':<20} {'Civilian':>10} {'Military':>10} {'Total':>10}")
    print("-" * 52)
    for faction in factions:
        print(f"{faction.name:<20} {faction.total_civilian_factories():>10} "
              f"{faction.total_military_factories():>10} {faction.total_factories():>10}")
    
    print("\nInfrastructure Comparison:")
    print(f"{'Faction':<20} {'Avg Infrastructure':>20}")
    print("-" * 42)
    for faction in factions:
        print(f"{faction.name:<20} {faction.average_infrastructure():>20.2f}")
    
    print()
    print("=" * 60)
    print("Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
