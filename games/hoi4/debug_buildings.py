"""
Debug script to check specific building parsing.
"""

import sys
from pathlib import Path

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent.parent))

from games.hoi4.parsers.building_parser import BuildingParser


def main():
    parser = BuildingParser()
    
    file_path = Path("games/hoi4/data/buildings/00_buildings.txt")
    if file_path.exists():
        print(f"Parsing {file_path}")
        buildings = parser.parse_file(file_path)
        
        print(f"\\nFound {len(buildings)} buildings:")
        for name, building in buildings.items():
            print(f"\\n{name}:")
            for key, value in building.items():
                if isinstance(value, dict):
                    print(f"  {key}: {{...}} (dict with {len(value)} items)")
                else:
                    print(f"  {key}: {value}")
        
        # Check if infrastructure exists
        if 'infrastructure' in buildings:
            print(f"\\nInfrastructure building found!")
            infra = buildings['infrastructure']
            print(f"Infrastructure details: {infra}")
        else:
            print(f"\\nInfrastructure building NOT found")
            print(f"Available buildings: {list(buildings.keys())}")
    else:
        print(f"File not found: {file_path}")


if __name__ == "__main__":
    main()
