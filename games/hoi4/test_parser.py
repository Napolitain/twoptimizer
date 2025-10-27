"""
Test script for HOI4 building parser.

Tests the parser on actual game data files.
"""

import sys
from pathlib import Path

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent.parent))

from games.hoi4.parsers.building_parser import BuildingParser
from games.hoi4.models.building import BuildingType, BuildingCategory


def test_building_parser():
    """Test the building parser on real game data."""
    
    # Initialize parser
    parser = BuildingParser()
    
    # Parse building files
    data_dir = Path("games/hoi4/data/buildings")
    
    if not data_dir.exists():
        print(f"Data directory not found: {data_dir}")
        return
    
    print("Parsing building files...")
    buildings_data = parser.parse_directory(data_dir)
    
    print(f"Parsed {len(buildings_data)} files")
    
    # Get all buildings
    all_buildings = parser.get_all_buildings()
    print(f"Found {len(all_buildings)} building types")
    
    # Print some example buildings
    print("\\nExample buildings:")
    for i, (name, building) in enumerate(all_buildings.items()):
        if i >= 5:  # Only show first 5
            break
        print(f"  {name}:")
        print(f"    Cost: {building.get('base_cost', 'N/A')}")
        print(f"    Infrastructure: {building.get('infrastructure', False)}")
        if building.get('country_modifiers'):
            print(f"    Country modifiers: {building['country_modifiers']}")
        if building.get('state_modifiers'):
            print(f"    State modifiers: {building['state_modifiers']}")
        print()
    
    # Test specific building lookups
    try:
        infrastructure = parser.get_building('infrastructure')
        print(f"Infrastructure building: {infrastructure}")
    except KeyError:
        print("Infrastructure building not found")
    
    # Get factory buildings
    factories = parser.get_factory_buildings()
    print(f"\\nFound {len(factories)} factory buildings:")
    for name in factories.keys():
        print(f"  - {name}")
    
    # Get infrastructure buildings
    infra_buildings = parser.get_infrastructure_buildings()
    print(f"\\nFound {len(infra_buildings)} infrastructure buildings:")
    for name in infra_buildings.keys():
        print(f"  - {name}")


if __name__ == "__main__":
    test_building_parser()
